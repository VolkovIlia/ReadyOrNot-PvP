#include "Types.h"

namespace RonComp
{
    const char* ToString(Side side)
    {
        switch (side)
        {
        case Side::Attackers: return "Attackers";
        case Side::Defenders: return "Defenders";
        }
        return "?";
    }

    const char* ToString(Faction faction)
    {
        switch (faction)
        {
        case Faction::Suspects: return "Suspects";
        case Faction::Swat: return "SWAT";
        }
        return "?";
    }

    const char* ToString(Phase phase)
    {
        switch (phase)
        {
        case Phase::Idle: return "Idle";
        case Phase::Warmup: return "Warmup";
        case Phase::FreezeTime: return "FreezeTime";
        case Phase::Live: return "Live";
        case Phase::BombPlanted: return "BombPlanted";
        case Phase::RoundEnd: return "RoundEnd";
        case Phase::Halftime: return "Halftime";
        case Phase::MatchEnd: return "MatchEnd";
        }
        return "?";
    }

    const char* ToString(RoundEndReason reason)
    {
        switch (reason)
        {
        case RoundEndReason::None: return "None";
        case RoundEndReason::AttackersEliminated: return "AttackersEliminated";
        case RoundEndReason::DefendersEliminated: return "DefendersEliminated";
        case RoundEndReason::TimeExpired: return "TimeExpired";
        case RoundEndReason::BombExploded: return "BombExploded";
        case RoundEndReason::BombDefused: return "BombDefused";
        }
        return "?";
    }
}
