#pragma once

// Shared vocabulary of the rules core. No Unreal or UE4SS types here: the core must build and be
// unit-tested on its own, and the adapters translate between these types and the game.

#include <cstdint>

namespace RonComp
{
    using PlayerId = std::uint32_t;
    constexpr PlayerId InvalidPlayer = 0;

    constexpr int NoTeam = -1;
    constexpr int TeamCount = 2;

    // Sides are roles within a round, like T/CT in Counter-Strike. Teams keep their score across
    // side swaps; which faction plays which side is a setting (mp_attackers_faction).
    enum class Side : std::uint8_t
    {
        Attackers = 0, // plant the bomb (CS: T)
        Defenders = 1, // guard sites and defuse (CS: CT)
    };

    enum class Faction : std::uint8_t
    {
        Suspects = 0,
        Swat = 1,
    };

    enum class Phase : std::uint8_t
    {
        Idle,
        Warmup,
        FreezeTime,
        Live,
        BombPlanted,
        RoundEnd,
        Halftime,
        MatchEnd,
    };

    enum class RoundEndReason : std::uint8_t
    {
        None,
        AttackersEliminated,
        DefendersEliminated,
        TimeExpired,
        BombExploded,
        BombDefused,
    };

    inline Side Opposite(Side side)
    {
        return side == Side::Attackers ? Side::Defenders : Side::Attackers;
    }

    inline int OtherTeam(int team)
    {
        return team == 0 ? 1 : 0;
    }

    const char* ToString(Side side);
    const char* ToString(Faction faction);
    const char* ToString(Phase phase);
    const char* ToString(RoundEndReason reason);
}
