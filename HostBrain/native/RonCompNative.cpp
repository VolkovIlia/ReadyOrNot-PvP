// RonCompNative: host-side native guards for Ready or Not that UE4SS Lua cannot express.
//
// The HostBrain Lua mod loads this DLL with package.loadlib(). The exported entry point has the
// lua_CFunction shape but never touches the Lua state (UE4SS does not export the Lua C API), so it
// reads its input from RonCompNative.ini and reports through RonCompNative.log, both next to the DLL.
//
// Guard: AReadyOrNotGameState::Multicast_StopSequence(nullptr).
//   The PvP round reset (ReadyOrNotGameMode_PVP, used by Firefight, TDM and Defusal) always calls
//   GameState->Multicast_StopSequence(nullptr); the implementation dereferences the actor and the
//   host crashes, and so would every client receiving the multicast. The native call stub is
//   detoured so that null calls return before ProcessEvent, i.e. before the RPC is ever sent.
//   See docs/re-findings.md for the call chain and the stub layout.
//
// Filter: SWAT-only server RPCs (yell, reports to TOC, arrests, orders to civilians, interactions
//   with characters) are dropped when a suspect player's character sends them (PvP and the solo
//   suspect mode); see InstallRpcFilter.
//
// Co-op PvP rules: the team rules ignore the hidden co-op PvP flag (otherwise civilians become
//   everybody's enemy and the AI shoots them), and score popups are dropped during a PvP match;
//   see InstallTeamRulesPatch and InstallDisplayScoreGuard.

#include <windows.h>

#include <atomic>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <utility>
#include <vector>

namespace
{
    // ------------------------------------------------------------------ logging and config

    std::wstring ModuleDirectory()
    {
        HMODULE self = nullptr;
        GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           reinterpret_cast<LPCWSTR>(&ModuleDirectory), &self);
        wchar_t path[MAX_PATH] = {};
        GetModuleFileNameW(self, path, MAX_PATH);
        std::wstring directory(path);
        const size_t slash = directory.find_last_of(L"\\/");
        return slash == std::wstring::npos ? L"." : directory.substr(0, slash);
    }

    // Diagnostics that bypass the CRT: appends one line to %TEMP%\RonCompNative_debug.log.
    void DebugTrace(const char* format, ...)
    {
        char line[512];
        va_list args;
        va_start(args, format);
        const int length = std::vsnprintf(line, sizeof(line) - 2, format, args);
        va_end(args);
        if (length <= 0)
        {
            return;
        }
        const size_t size = static_cast<size_t>(length) < sizeof(line) - 2 ? static_cast<size_t>(length) : sizeof(line) - 2;
        line[size] = '\r';
        line[size + 1] = '\n';
        wchar_t temp[MAX_PATH] = {};
        GetTempPathW(MAX_PATH, temp);
        const std::wstring path = std::wstring(temp) + L"RonCompNative_debug.log";
        HANDLE file = CreateFileW(path.c_str(), FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_ALWAYS,
                                  FILE_ATTRIBUTE_NORMAL, nullptr);
        if (file == INVALID_HANDLE_VALUE)
        {
            return;
        }
        DWORD written = 0;
        WriteFile(file, line, static_cast<DWORD>(size + 2), &written, nullptr);
        CloseHandle(file);
    }

    void Log(const char* format, ...)
    {
        // _wfopen_s opens without sharing, so any reader (the Lua side, a tail) would make the write
        // fail; _wfsopen with _SH_DENYNO lets the log be read while it is written.
        const std::wstring path = ModuleDirectory() + L"\\RonCompNative.log";
        FILE* file = _wfsopen(path.c_str(), L"a", _SH_DENYNO);
        if (!file)
        {
            DebugTrace("Log: cannot open RonCompNative.log errno=%d lasterror=%lu", errno, GetLastError());
            return;
        }
        SYSTEMTIME now;
        GetLocalTime(&now);
        std::fprintf(file, "%02d:%02d:%02d ", now.wHour, now.wMinute, now.wSecond);
        va_list args;
        va_start(args, format);
        std::vfprintf(file, format, args);
        va_end(args);
        std::fputc('\n', file);
        std::fclose(file);
    }

    // Values written by the Lua side are ASCII, so narrowing them is lossless.
    std::string ReadIniString(const wchar_t* key, const wchar_t* section = L"guards")
    {
        const std::wstring path = ModuleDirectory() + L"\\RonCompNative.ini";
        wchar_t text[128] = {};
        GetPrivateProfileStringW(section, key, L"", text, 128, path.c_str());
        std::string value;
        for (const wchar_t* c = text; *c; ++c)
        {
            value.push_back(*c < 128 ? static_cast<char>(*c) : '?');
        }
        return value;
    }

    bool ReadIniUInt64(const wchar_t* key, uint64_t& out, const wchar_t* section = L"guards")
    {
        const std::wstring path = ModuleDirectory() + L"\\RonCompNative.ini";
        wchar_t text[32] = {};
        GetPrivateProfileStringW(section, key, L"", text, 32, path.c_str());
        if (text[0] == L'\0')
        {
            return false;
        }
        wchar_t* end = nullptr;
        const unsigned long long value = std::wcstoull(text, &end, 10);
        if (end == text || *end != L'\0')
        {
            return false;
        }
        out = static_cast<uint64_t>(value);
        return true;
    }

    bool ReadIniUInt(const wchar_t* key, uint32_t& out, const wchar_t* section = L"guards")
    {
        uint64_t value = 0;
        if (!ReadIniUInt64(key, value, section) || value > 0xFFFFFFFFull)
        {
            return false;
        }
        out = static_cast<uint32_t>(value);
        return true;
    }

    // ------------------------------------------------------------------ code scanning

    struct CodeRange
    {
        uint8_t* Begin = nullptr;
        uint8_t* End = nullptr;
    };

    CodeRange TextSection(HMODULE module)
    {
        auto* base = reinterpret_cast<uint8_t*>(module);
        const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
        const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
        const IMAGE_SECTION_HEADER* section = IMAGE_FIRST_SECTION(nt);
        for (WORD i = 0; i < nt->FileHeader.NumberOfSections; ++i, ++section)
        {
            if (std::memcmp(section->Name, ".text", 5) == 0)
            {
                return {base + section->VirtualAddress, base + section->VirtualAddress + section->Misc.VirtualSize};
            }
        }
        return {};
    }

    // -1 marks a wildcard byte.
    std::vector<uint8_t*> FindPattern(const CodeRange& range, const int16_t* pattern, size_t length)
    {
        std::vector<uint8_t*> matches;
        if (!range.Begin || static_cast<size_t>(range.End - range.Begin) < length)
        {
            return matches;
        }
        for (uint8_t* at = range.Begin; at + length <= range.End; ++at)
        {
            if (*at != pattern[0])
            {
                continue;
            }
            size_t i = 1;
            while (i < length && (pattern[i] < 0 || at[i] == static_cast<uint8_t>(pattern[i])))
            {
                ++i;
            }
            if (i == length)
            {
                matches.push_back(at);
            }
        }
        return matches;
    }

    // ------------------------------------------------------------------ detour

    // Replaces the first PrologueSize bytes of target with an absolute jump to hook. Those bytes must
    // be whole, position-independent instructions (the pattern guarantees it); they are copied to a
    // trampoline followed by a jump back, so calling the trampoline runs the original function.
    constexpr size_t PrologueSize = 16;
    constexpr size_t AbsoluteJumpSize = 14; // FF 25 00000000 <imm64>

    void WriteAbsoluteJump(uint8_t* at, const void* destination)
    {
        at[0] = 0xFF;
        at[1] = 0x25;
        std::memset(at + 2, 0, 4);
        const uint64_t address = reinterpret_cast<uint64_t>(destination);
        std::memcpy(at + 6, &address, sizeof(address));
    }

    void* InstallDetour(uint8_t* target, const void* hook)
    {
        auto* trampoline = static_cast<uint8_t*>(
            VirtualAlloc(nullptr, PrologueSize + AbsoluteJumpSize, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
        if (!trampoline)
        {
            return nullptr;
        }
        std::memcpy(trampoline, target, PrologueSize);
        WriteAbsoluteJump(trampoline + PrologueSize, target + PrologueSize);

        DWORD oldProtection = 0;
        if (!VirtualProtect(target, PrologueSize, PAGE_EXECUTE_READWRITE, &oldProtection))
        {
            VirtualFree(trampoline, 0, MEM_RELEASE);
            return nullptr;
        }
        WriteAbsoluteJump(target, hook);
        std::memset(target + AbsoluteJumpSize, 0x90, PrologueSize - AbsoluteJumpSize);
        DWORD ignored = 0;
        VirtualProtect(target, PrologueSize, oldProtection, &ignored);
        FlushInstructionCache(GetCurrentProcess(), target, PrologueSize);
        return trampoline;
    }

    // ------------------------------------------------------------------ StopSequence guard

    // Native stub generated for a one-pointer-parameter UFunction event, e.g.
    //   void AReadyOrNotGameState::Multicast_StopSequence(ALevelSequenceActor* SequenceActor)
    // It stores the argument, finds the UFunction by FName (global at the rip-relative operand) and
    // calls ProcessEvent through vtable slot 0x268. Many stubs share this shape; the FName global
    // tells them apart.
    const int16_t EventStubPattern[] = {
        0x48, 0x89, 0x5C, 0x24, 0x10,             // mov [rsp+10h], rbx
        0x57,                                     // push rdi
        0x48, 0x83, 0xEC, 0x20,                   // sub rsp, 20h
        0x48, 0x8B, 0x01,                         // mov rax, [rcx]
        0x48, 0x8B, 0xF9,                         // mov rdi, rcx
        0x48, 0x89, 0x54, 0x24, 0x30,             // mov [rsp+30h], rdx
        0x48, 0x8B, 0x15, -1, -1, -1, -1,         // mov rdx, [rip+FName]
        0x48, 0x8B, 0x98, 0x68, 0x02, 0x00, 0x00, // mov rbx, [rax+268h]  (ProcessEvent)
        0xE8, -1, -1, -1, -1,                     // call FindFunctionChecked
        0x4C, 0x8D, 0x44, 0x24, 0x30,             // lea r8, [rsp+30h]
        0x48, 0x8B, 0xD0,                         // mov rdx, rax
        0x48, 0x8B, 0xCF,                         // mov rcx, rdi
        0xFF, 0xD3,                               // call rbx
    };
    constexpr size_t EventStubFNameOperand = 24;
    constexpr size_t EventStubFNameNextInstruction = 28;

    struct FNameValue
    {
        uint32_t ComparisonIndex;
        uint32_t Number;
    };

    FNameValue StubFName(const uint8_t* stub)
    {
        int32_t displacement = 0;
        std::memcpy(&displacement, stub + EventStubFNameOperand, sizeof(displacement));
        const uint8_t* global = stub + EventStubFNameNextInstruction + displacement;
        FNameValue name{};
        std::memcpy(&name, global, sizeof(name));
        return name;
    }

    using StopSequenceFunction = void (*)(void* gameState, void* sequenceActor);
    StopSequenceFunction g_OriginalStopSequence = nullptr;
    uint8_t* g_StopSequenceStub = nullptr;
    std::atomic<uint32_t> g_BlockedStopSequence{0};

    void StopSequenceGuard(void* gameState, void* sequenceActor)
    {
        if (sequenceActor == nullptr)
        {
            Log("blocked Multicast_StopSequence(nullptr) #%u", ++g_BlockedStopSequence);
            return;
        }
        g_OriginalStopSequence(gameState, sequenceActor);
    }

    bool InstallStopSequenceGuard()
    {
        uint32_t fnameIndex = 0;
        if (!ReadIniUInt(L"stop_sequence_fname_index", fnameIndex))
        {
            Log("ERROR stop_sequence_fname_index missing in RonCompNative.ini");
            return false;
        }

        const CodeRange text = TextSection(GetModuleHandleW(nullptr));
        const std::vector<uint8_t*> stubs = FindPattern(text, EventStubPattern, sizeof(EventStubPattern) / sizeof(EventStubPattern[0]));
        std::vector<uint8_t*> matches;
        for (uint8_t* stub : stubs)
        {
            const FNameValue name = StubFName(stub);
            if (name.ComparisonIndex == fnameIndex && name.Number == 0)
            {
                matches.push_back(stub);
            }
        }
        Log("event stubs found: %zu, matching Multicast_StopSequence (fname %u): %zu", stubs.size(), fnameIndex, matches.size());
        if (matches.size() != 1)
        {
            Log("ERROR expected exactly one Multicast_StopSequence stub; guard NOT installed");
            return false;
        }

        void* trampoline = InstallDetour(matches[0], reinterpret_cast<const void*>(&StopSequenceGuard));
        if (!trampoline)
        {
            Log("ERROR could not patch the stub; guard NOT installed");
            return false;
        }
        g_OriginalStopSequence = reinterpret_cast<StopSequenceFunction>(trampoline);
        g_StopSequenceStub = matches[0];
        const auto rva = static_cast<unsigned long long>(matches[0] - reinterpret_cast<uint8_t*>(GetModuleHandleW(nullptr)));
        Log("OK StopSequence guard installed at exe+0x%llx", rva);
        return true;
    }

    // Calls the patched stub the way the game does, with a null actor, and expects the guard to
    // swallow it. Only runs when the stub provably starts with our jump: calling the unpatched stub
    // with a null GameState would crash.
    bool SelfTestStopSequenceGuard()
    {
        if (!g_StopSequenceStub)
        {
            return false;
        }
        uint64_t jumpTarget = 0;
        std::memcpy(&jumpTarget, g_StopSequenceStub + 6, sizeof(jumpTarget));
        if (g_StopSequenceStub[0] != 0xFF || g_StopSequenceStub[1] != 0x25
            || jumpTarget != reinterpret_cast<uint64_t>(&StopSequenceGuard))
        {
            Log("SELFTEST failed: the stub does not jump to the guard");
            return false;
        }
        const uint32_t before = g_BlockedStopSequence.load();
        reinterpret_cast<StopSequenceFunction>(g_StopSequenceStub)(nullptr, nullptr);
        const bool passed = g_BlockedStopSequence.load() == before + 1;
        Log(passed ? "SELFTEST ok: null StopSequence through the game's stub was blocked"
                   : "SELFTEST failed: the guard did not see the call");
        return passed;
    }

    // ------------------------------------------------------------------ co-op PvP rules

    // While HostBrain runs a PvP match it switches g_PvpActive (RonCompNative_PvpOn / _PvpOff).
    std::atomic<bool> g_PvpActive{false};

    // Team rules. With the hidden co-op PvP flag (CoopGS.bCrouchingTigerHiddenDragon) the game's
    // IsEnemyTeam(A, B) becomes "A != B" and IsFriendlyTeam "A == B". Civilians (TT_CIVILIAN) then
    // turn into enemies of the AI SWAT squad and of the AI suspects, which shoot them. Each of the
    // three functions starts by asking for the flag; the patch makes them use the ordinary rules
    // (SWAT vs suspects, civilians neutral) while the flag still drives spectating and team view.
    //   IsEnemyTeam:    call flag; test al,al; jz ordinary  ->  jmp ordinary
    //   IsFriendlyTeam: call flag; test al,al; jnz by-team  ->  xor al,al; nop; nop (AL is compared next)
    const int16_t EnemyTeamFlagCheck[] = {
        0xE8, -1, -1, -1, -1, // call IsSecretPvP
        0x84, 0xC0,           // test al, al
        0x74, 0x11,           // jz ordinary rules
        0x40, 0x3A, 0xFB,     // cmp dil, bl
        0x0F, 0x95, 0xC0,     // setnz al
    };
    const int16_t FriendlyTeamFlagCheck[] = {
        0xE8, -1, -1, -1, -1,             // call IsSecretPvP
        0x84, 0xC0,                       // test al, al
        0x75, 0x4D,                       // jnz compare teams
        0x38, 0x86, 0x40, 0x08, 0x00, 0x00, // cmp [rsi+840h], al
    };

    const uint8_t* CallTarget(const uint8_t* call)
    {
        int32_t displacement = 0;
        std::memcpy(&displacement, call + 1, sizeof(displacement));
        return call + 5 + displacement;
    }

    bool WriteCode(uint8_t* at, const uint8_t* bytes, size_t length)
    {
        DWORD oldProtection = 0;
        if (!VirtualProtect(at, length, PAGE_EXECUTE_READWRITE, &oldProtection))
        {
            return false;
        }
        std::memcpy(at, bytes, length);
        DWORD ignored = 0;
        VirtualProtect(at, length, oldProtection, &ignored);
        FlushInstructionCache(GetCurrentProcess(), at, length);
        return true;
    }

    bool InstallTeamRulesPatch()
    {
        const CodeRange text = TextSection(GetModuleHandleW(nullptr));
        const auto enemy = FindPattern(text, EnemyTeamFlagCheck, sizeof(EnemyTeamFlagCheck) / sizeof(EnemyTeamFlagCheck[0]));
        const auto friendly = FindPattern(text, FriendlyTeamFlagCheck, sizeof(FriendlyTeamFlagCheck) / sizeof(FriendlyTeamFlagCheck[0]));
        Log("team rules: IsEnemyTeam flag checks %zu, IsFriendlyTeam flag checks %zu", enemy.size(), friendly.size());
        if (enemy.size() != 1 || friendly.size() != 2)
        {
            Log("ERROR expected 1 + 2 flag checks; team rules NOT patched");
            return false;
        }
        const uint8_t* flag = CallTarget(enemy[0]);
        if (CallTarget(friendly[0]) != flag || CallTarget(friendly[1]) != flag)
        {
            Log("ERROR the flag checks call different functions; team rules NOT patched");
            return false;
        }
        const uint8_t jump = 0xEB;
        const uint8_t clear[] = {0x32, 0xC0, 0x90, 0x90};
        bool ok = WriteCode(enemy[0] + 7, &jump, 1);
        ok = ok && WriteCode(friendly[0] + 5, clear, sizeof(clear));
        ok = ok && WriteCode(friendly[1] + 5, clear, sizeof(clear));
        const auto* base = reinterpret_cast<uint8_t*>(GetModuleHandleW(nullptr));
        Log(ok ? "OK team rules ignore the co-op PvP flag (exe+0x%llx, +0x%llx, +0x%llx)"
               : "ERROR could not write the team rules patch (exe+0x%llx, +0x%llx, +0x%llx)",
            static_cast<unsigned long long>(enemy[0] - base), static_cast<unsigned long long>(friendly[0] - base),
            static_cast<unsigned long long>(friendly[1] - base));
        return ok;
    }

    // Score popups. AScoringManager::Multicast_DisplayScore(const FText&, int32, bool) shows "+N <score>"
    // on every player's HUD; in PvP the suspects would see SWAT's mission score. Its native stub calls
    // ProcessEvent (which sends the multicast), so the detour drops the popup for everyone while PvP is
    // on. The stub is the function that loads the FName global holding Multicast_DisplayScore
    // (mov rdx, [rip+name]); its 16-byte prologue is copied to the trampoline.
    const uint8_t DisplayScorePrologue[] = {
        0x48, 0x89, 0x5C, 0x24, 0x08, // mov [rsp+8], rbx
        0x48, 0x89, 0x6C, 0x24, 0x10, // mov [rsp+10h], rbp
        0x48, 0x89, 0x74, 0x24, 0x18, // mov [rsp+18h], rsi
        0x57,                         // push rdi
    };

    using DisplayScoreFunction = void (*)(void* manager, void* text, int32_t score, bool give);
    DisplayScoreFunction g_OriginalDisplayScore = nullptr;
    std::atomic<uint32_t> g_BlockedScores{0};

    void DisplayScoreGuard(void* manager, void* text, int32_t score, bool give)
    {
        if (g_PvpActive.load())
        {
            const uint32_t blocked = ++g_BlockedScores;
            if (blocked <= 5 || blocked % 50 == 0)
            {
                Log("blocked score popup %d during PvP #%u", score, blocked);
            }
            return;
        }
        g_OriginalDisplayScore(manager, text, score, give);
    }

    bool InstallDisplayScoreGuard()
    {
        uint32_t fnameIndex = 0;
        if (!ReadIniUInt(L"display_score_fname_index", fnameIndex))
        {
            Log("ERROR display_score_fname_index missing in RonCompNative.ini");
            return false;
        }
        auto* base = reinterpret_cast<uint8_t*>(GetModuleHandleW(nullptr));
        const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(base + reinterpret_cast<const IMAGE_DOS_HEADER*>(base)->e_lfanew);
        const uint8_t* imageEnd = base + nt->OptionalHeader.SizeOfImage;
        const CodeRange text = TextSection(GetModuleHandleW(nullptr));
        const int16_t loadName[] = {0x48, 0x8B, 0x15, -1, -1, -1, -1}; // mov rdx, [rip+disp32]
        std::vector<uint8_t*> stubs;
        for (uint8_t* load : FindPattern(text, loadName, 7))
        {
            int32_t displacement = 0;
            std::memcpy(&displacement, load + 3, sizeof(displacement));
            const uint8_t* global = load + 7 + displacement;
            if (global < base || global + sizeof(FNameValue) > imageEnd || (global >= text.Begin && global < text.End))
            {
                continue;
            }
            FNameValue name{};
            std::memcpy(&name, global, sizeof(name));
            if (name.ComparisonIndex != fnameIndex || name.Number != 0)
            {
                continue;
            }
            DWORD64 imageBase = 0;
            const RUNTIME_FUNCTION* entry = RtlLookupFunctionEntry(reinterpret_cast<DWORD64>(load), &imageBase, nullptr);
            if (entry)
            {
                stubs.push_back(reinterpret_cast<uint8_t*>(imageBase + entry->BeginAddress));
            }
        }
        Log("Multicast_DisplayScore (fname %u): %zu loading function(s)", fnameIndex, stubs.size());
        if (stubs.size() != 1 || std::memcmp(stubs[0], DisplayScorePrologue, sizeof(DisplayScorePrologue)) != 0)
        {
            Log("ERROR expected one stub with the known prologue; score popup guard NOT installed");
            return false;
        }
        void* trampoline = InstallDetour(stubs[0], reinterpret_cast<const void*>(&DisplayScoreGuard));
        if (!trampoline)
        {
            Log("ERROR could not patch the score popup stub");
            return false;
        }
        g_OriginalDisplayScore = reinterpret_cast<DisplayScoreFunction>(trampoline);
        Log("OK score popup guard installed at exe+0x%llx", static_cast<unsigned long long>(stubs[0] - base));
        return true;
    }

    bool g_PvpRulesInstalled = false;

    bool g_Installed = false;

    // ------------------------------------------------------------------ suspect RPC filter

    // Server RPCs that only SWAT may use (yelling compliance, reports to TOC, arrests, orders to
    // civilians, interactions with characters). A suspect player keeps every other interaction: doors,
    // ladders, items. The filter replaces UFunction::Func, the native exec thunk ProcessEvent invokes
    // for the RPC; a blocked call returns before the RPC's _Validate, so the sender is not kicked for a
    // failed validation.
    using NativeFunction = void (*)(void* context, void* stack, void* result);

    constexpr int MaxFiltered = 16;
    constexpr size_t ObjectClassOffset = 0x10; // UObjectBase::ClassPrivate
    constexpr size_t ObjectOuterOffset = 0x20; // UObjectBase::OuterPrivate (a component's owner)
    constexpr size_t FrameCodeOffset = 0x20;   // FFrame::Code: null when ProcessEvent passes Parms
    constexpr size_t FrameLocalsOffset = 0x28; // FFrame::Locals: the Parms buffer

    enum class FilterMode : int
    {
        Always = 0,          // block for suspects
        CharacterTarget = 1, // block for suspects when the first or second parameter is a character
    };

    struct FilteredFunction
    {
        NativeFunction Original = nullptr;
        FilterMode Mode = FilterMode::Always;
        char Name[64] = {};
        std::atomic<uint32_t> Blocked{0};
        std::atomic<uint32_t> ScriptCalls{0};
    };

    FilteredFunction g_Filtered[MaxFiltered];
    int g_FilteredCount = 0;
    size_t g_TeamOffset = 0;   // AReadyOrNotCharacter::DefaultTeam
    uint8_t g_BlockedTeam = 3; // ETeamType::TT_SUSPECT
    const void* g_CharacterClass = nullptr;
    size_t g_SuperOffset = 0;  // UStruct::SuperStruct, found at install time
    bool g_FilterInstalled = false;

    const void* ReadPointer(const void* base, size_t offset)
    {
        return *reinterpret_cast<const void* const*>(static_cast<const uint8_t*>(base) + offset);
    }

    bool IsCharacter(const void* object)
    {
        if (!object)
        {
            return false;
        }
        const void* cls = ReadPointer(object, ObjectClassOffset);
        for (int depth = 0; cls && depth < 64; ++depth)
        {
            if (cls == g_CharacterClass)
            {
                return true;
            }
            cls = ReadPointer(cls, g_SuperOffset);
        }
        return false;
    }

    // The object itself or, for a component, the actor that owns it.
    bool IsOrBelongsToCharacter(const void* object)
    {
        return object && (IsCharacter(object) || IsCharacter(ReadPointer(object, ObjectOuterOffset)));
    }

    template <int N>
    void FilterThunk(void* context, void* stack, void* result)
    {
        FilteredFunction& filtered = g_Filtered[N];
        if (context && *(static_cast<const uint8_t*>(context) + g_TeamOffset) == g_BlockedTeam)
        {
            if (ReadPointer(stack, FrameCodeOffset) != nullptr)
            {
                // called from blueprint bytecode: the parameters still sit in the caller's code and
                // must be consumed by the original thunk, so this call cannot be dropped
                const uint32_t calls = ++filtered.ScriptCalls;
                if (calls <= 3)
                {
                    Log("not filtered (script call) %s from a suspect #%u", filtered.Name, calls);
                }
            }
            else
            {
                bool block = filtered.Mode == FilterMode::Always;
                if (!block)
                {
                    const auto* locals = static_cast<const uint8_t*>(ReadPointer(stack, FrameLocalsOffset));
                    block = locals && (IsOrBelongsToCharacter(ReadPointer(locals, 0)) || IsOrBelongsToCharacter(ReadPointer(locals, 8)));
                }
                if (block)
                {
                    const uint32_t blocked = ++filtered.Blocked;
                    if (blocked <= 5 || blocked % 50 == 0)
                    {
                        Log("blocked %s from a suspect #%u", filtered.Name, blocked);
                    }
                    return;
                }
            }
        }
        filtered.Original(context, stack, result);
    }

    template <int... N>
    constexpr NativeFunction ThunkAt(int index, std::integer_sequence<int, N...>)
    {
        constexpr NativeFunction thunks[] = {&FilterThunk<N>...};
        return thunks[index];
    }

    NativeFunction Thunk(int index)
    {
        return ThunkAt(index, std::make_integer_sequence<int, MaxFiltered>{});
    }

    // Offset of a pointer-sized field of object whose value is expected, searched in [from, to).
    bool FindPointerField(const void* object, const void* expected, size_t from, size_t to, size_t& offset)
    {
        int found = 0;
        for (size_t at = from; at < to; at += sizeof(void*))
        {
            if (ReadPointer(object, at) == expected)
            {
                offset = at;
                ++found;
            }
        }
        return found == 1;
    }

    // UFunction::Func is the only field of a native UFunction pointing into the game's code.
    bool FindExecField(const void* function, const CodeRange& text, size_t& offset)
    {
        int found = 0;
        for (size_t at = 0x30; at < 0x140; at += sizeof(void*))
        {
            const auto* value = static_cast<const uint8_t*>(ReadPointer(function, at));
            if (value >= text.Begin && value < text.End)
            {
                offset = at;
                ++found;
            }
        }
        return found == 1;
    }

    bool InstallRpcFilter()
    {
        const wchar_t* section = L"rpc_filter";
        uint64_t teamOffset = 0, blockedTeam = 0, characterClass = 0, characterSuper = 0, probePawn = 0, probeTeam = 0, count = 0;
        if (!ReadIniUInt64(L"team_offset", teamOffset, section) || !ReadIniUInt64(L"blocked_team", blockedTeam, section)
            || !ReadIniUInt64(L"character_class", characterClass, section) || !ReadIniUInt64(L"character_super", characterSuper, section)
            || !ReadIniUInt64(L"probe_pawn", probePawn, section) || !ReadIniUInt64(L"probe_team", probeTeam, section)
            || !ReadIniUInt64(L"count", count, section) || count == 0 || count > MaxFiltered)
        {
            Log("ERROR [rpc_filter] in RonCompNative.ini is incomplete");
            return false;
        }
        g_TeamOffset = static_cast<size_t>(teamOffset);
        g_BlockedTeam = static_cast<uint8_t>(blockedTeam);
        g_CharacterClass = reinterpret_cast<const void*>(characterClass);
        if (!FindPointerField(g_CharacterClass, reinterpret_cast<const void*>(characterSuper), 0x28, 0x100, g_SuperOffset))
        {
            Log("ERROR UStruct::SuperStruct not found in the character class; filter NOT installed");
            return false;
        }

        // Self-test on the host's living pawn: it must be a character and its team must read as Lua sees it.
        const void* pawn = reinterpret_cast<const void*>(probePawn);
        const uint8_t team = *(static_cast<const uint8_t*>(pawn) + g_TeamOffset);
        if (!IsCharacter(pawn) || team != probeTeam)
        {
            Log("ERROR self-test: host pawn character=%d team=%u (Lua: %llu); filter NOT installed", IsCharacter(pawn) ? 1 : 0,
                team, static_cast<unsigned long long>(probeTeam));
            return false;
        }

        const CodeRange text = TextSection(GetModuleHandleW(nullptr));
        struct Pending
        {
            void* Function;
            size_t ExecOffset;
        };
        std::vector<Pending> pending;
        for (uint64_t i = 0; i < count; ++i)
        {
            const std::wstring index = std::to_wstring(i);
            uint64_t function = 0, mode = 0;
            const std::string name = ReadIniString((L"name_" + index).c_str(), section);
            if (!ReadIniUInt64((L"function_" + index).c_str(), function, section) || !ReadIniUInt64((L"mode_" + index).c_str(), mode, section)
                || function == 0 || mode > 1)
            {
                Log("ERROR rpc_filter entry %llu is incomplete; filter NOT installed", static_cast<unsigned long long>(i));
                return false;
            }
            size_t execOffset = 0;
            if (!FindExecField(reinterpret_cast<const void*>(function), text, execOffset))
            {
                Log("ERROR no unique native exec pointer in UFunction %s; filter NOT installed", name.c_str());
                return false;
            }
            FilteredFunction& filtered = g_Filtered[i];
            filtered.Mode = static_cast<FilterMode>(mode);
            std::snprintf(filtered.Name, sizeof(filtered.Name), "%s", name.c_str());
            pending.push_back({reinterpret_cast<void*>(function), execOffset});
        }
        // Swap only after every entry checked out, so the filter is all or nothing.
        for (size_t i = 0; i < pending.size(); ++i)
        {
            auto* slot = reinterpret_cast<NativeFunction*>(static_cast<uint8_t*>(pending[i].Function) + pending[i].ExecOffset);
            g_Filtered[i].Original = *slot;
            *slot = Thunk(static_cast<int>(i));
            Log("filtering %s (UFunction+0x%zx, original exe+0x%llx)", g_Filtered[i].Name, pending[i].ExecOffset,
                static_cast<unsigned long long>(reinterpret_cast<uint8_t*>(g_Filtered[i].Original) - reinterpret_cast<uint8_t*>(GetModuleHandleW(nullptr))));
        }
        g_FilteredCount = static_cast<int>(pending.size());
        Log("OK suspect RPC filter installed: %d functions, team at +0x%zx, SuperStruct at +0x%zx", g_FilteredCount, g_TeamOffset, g_SuperOffset);
        return true;
    }
}

// Called from Lua as package.loadlib(dll, "RonCompNative_InstallGuards")(). Takes the lua_State*
// and returns 0 Lua results without touching it. Safe to call more than once.
//
// The module pins itself on the first call: when UE4SS restarts the Lua mod, Lua closes its state and
// FreeLibrary()s every library loaded with package.loadlib, but the game's stub keeps jumping into
// this DLL. Pinned, it stays mapped until the process exits, and a later loadlib gets this same
// instance (with g_Installed already set).
//
// The status line carries the session token Lua wrote into the ini, so Lua never mistakes a line
// from an earlier run for the answer to this call.
extern "C" __declspec(dllexport) int RonCompNative_InstallGuards(void* /*luaState*/)
{
    HMODULE pinned = nullptr;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
                            reinterpret_cast<LPCWSTR>(&RonCompNative_InstallGuards), &pinned))
    {
        DebugTrace("could not pin RonCompNative.dll lasterror=%lu", GetLastError());
    }

    const std::string token = ReadIniString(L"session_token");
    if (!g_Installed)
    {
        Log("---- RonCompNative: installing guards (pid %lu)", GetCurrentProcessId());
        g_Installed = InstallStopSequenceGuard() && SelfTestStopSequenceGuard();
        const bool teamRules = InstallTeamRulesPatch();
        const bool scores = InstallDisplayScoreGuard();
        g_PvpRulesInstalled = teamRules && scores;
    }
    else
    {
        Log("guards already installed in this process");
    }
    Log("PVPRULES %s %s", token.empty() ? "-" : token.c_str(), g_PvpRulesInstalled ? "ok" : "failed");
    Log("STATUS %s %s", token.empty() ? "-" : token.c_str(), g_Installed ? "ok" : "failed");
    return 0;
}

// PvP on/off for the guards that only act during a match (score popups). Called from Lua as
// package.loadlib(dll, "RonCompNative_PvpOn")() and "_PvpOff".
extern "C" __declspec(dllexport) int RonCompNative_PvpOn(void* /*luaState*/)
{
    if (!g_PvpActive.exchange(true))
    {
        Log("PvP on");
    }
    return 0;
}

extern "C" __declspec(dllexport) int RonCompNative_PvpOff(void* /*luaState*/)
{
    if (g_PvpActive.exchange(false))
    {
        Log("PvP off");
    }
    return 0;
}

// Called from Lua as package.loadlib(dll, "RonCompNative_InstallRpcFilter")() once the host has a
// living character (the self-test reads its team). Input: [rpc_filter] in RonCompNative.ini; answer:
// "STATUS <token> ok|failed" in RonCompNative.log. Installs once per process.
extern "C" __declspec(dllexport) int RonCompNative_InstallRpcFilter(void* /*luaState*/)
{
    HMODULE pinned = nullptr;
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
                       reinterpret_cast<LPCWSTR>(&RonCompNative_InstallRpcFilter), &pinned);

    const std::string token = ReadIniString(L"session_token", L"rpc_filter");
    if (!g_FilterInstalled)
    {
        Log("---- RonCompNative: installing the suspect RPC filter (pid %lu)", GetCurrentProcessId());
        g_FilterInstalled = InstallRpcFilter();
    }
    else
    {
        Log("suspect RPC filter already installed in this process");
    }
    Log("STATUS %s %s", token.empty() ? "-" : token.c_str(), g_FilterInstalled ? "ok" : "failed");
    return 0;
}
