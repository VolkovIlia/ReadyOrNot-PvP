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

#include <windows.h>

#include <atomic>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
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
    std::string ReadIniString(const wchar_t* key)
    {
        const std::wstring path = ModuleDirectory() + L"\\RonCompNative.ini";
        wchar_t text[128] = {};
        GetPrivateProfileStringW(L"guards", key, L"", text, 128, path.c_str());
        std::string value;
        for (const wchar_t* c = text; *c; ++c)
        {
            value.push_back(*c < 128 ? static_cast<char>(*c) : '?');
        }
        return value;
    }

    bool ReadIniUInt(const wchar_t* key, uint32_t& out)
    {
        const std::wstring path = ModuleDirectory() + L"\\RonCompNative.ini";
        wchar_t text[32] = {};
        GetPrivateProfileStringW(L"guards", key, L"", text, 32, path.c_str());
        if (text[0] == L'\0')
        {
            return false;
        }
        wchar_t* end = nullptr;
        const unsigned long value = std::wcstoul(text, &end, 10);
        if (end == text || *end != L'\0')
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

    bool g_Installed = false;
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
    }
    else
    {
        Log("guards already installed in this process");
    }
    Log("STATUS %s %s", token.empty() ? "-" : token.c_str(), g_Installed ? "ok" : "failed");
    return 0;
}
