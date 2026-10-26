#pragma once

#include "TestFramework.h"

#include "../src/core/Match.h"

#include <fstream>
#include <sstream>

// Printable core enums for CHECK_EQ messages (found by ADL).
namespace RonComp
{
    inline std::ostream& operator<<(std::ostream& out, Phase value) { return out << ToString(value); }
    inline std::ostream& operator<<(std::ostream& out, Side value) { return out << ToString(value); }
    inline std::ostream& operator<<(std::ostream& out, Faction value) { return out << ToString(value); }
    inline std::ostream& operator<<(std::ostream& out, RoundEndReason value) { return out << ToString(value); }
    inline std::ostream& operator<<(std::ostream& out, BuyResult value) { return out << ToString(value); }
    inline std::ostream& operator<<(std::ostream& out, EventType value) { return out << ToString(value); }
    inline std::ostream& operator<<(std::ostream& out, ItemCategory value) { return out << ToString(value); }
}

namespace TestHelpers
{
    inline std::string ReadFile(const std::string& path)
    {
        std::ifstream file(path, std::ios::binary);
        std::ostringstream content;
        content << file.rdbuf();
        return content.str();
    }

    inline bool FileExists(const std::string& path)
    {
        return std::ifstream(path).good();
    }

    // A small fixed catalog so match tests do not depend on balance changes in data/items.csv.
    inline const char* TestItemsCsv()
    {
        return "id,name,category,faction,price,kill_reward,max_carry,game_item\n"
               "usp,USP,pistol,swat,200,300,1,/Game/usp\n"
               "g19s,Glock,pistol,suspects,200,300,1,/Game/g19s\n"
               "m4a1,M4A1,rifle,swat,2900,300,1,/Game/m4a1\n"
               "akm,AKM,rifle,suspects,2700,300,1,/Game/akm\n"
               "mp9,MP9,smg,swat,1250,600,1,/Game/mp9\n"
               "m24,M24,marksman,any,4750,100,1,/Game/m24\n"
               "knife,Knife,melee,suspects,0,1500,1,/Game/knife\n"
               "armor_light,Light Armor,armor,any,650,0,1,/Game/armor\n"
               "flashbang,Flashbang,grenade,any,200,300,2,/Game/flash\n"
               "smoke,Smoke,grenade,any,300,300,1,/Game/smoke\n"
               "frag,Frag,grenade,suspects,300,300,1,/Game/frag\n"
               "stinger,Stinger,grenade,swat,300,300,1,/Game/stinger\n"
               "defuse_kit,Kit,kit,defenders,400,0,1,/Game/kit\n";
    }

    // Five players per team: team 0 = ids 1..5, team 1 = ids 6..10.
    struct Fixture
    {
        RonComp::Settings Settings;
        RonComp::ItemCatalog Items;
        RonComp::Match Match;

        Fixture()
            : Match(Settings, Items, 7)
        {
            Items.LoadFromCsv(TestItemsCsv());
            for (RonComp::PlayerId id = 1; id <= 10; ++id)
            {
                Match.AddPlayer(id, id <= 5 ? 0 : 1);
            }
        }

        int TeamOnSide(RonComp::Side side) const { return Match.GetTeamOnSide(side); }

        RonComp::PlayerId FirstAlive(RonComp::Side side) const
        {
            for (const RonComp::PlayerState& player : Match.GetPlayers())
            {
                if (player.Alive && player.Team != RonComp::NoTeam && Match.GetSide(player.Team) == side)
                {
                    return player.Id;
                }
            }
            return RonComp::InvalidPlayer;
        }

        const RonComp::PlayerState& Player(RonComp::PlayerId id) const { return *Match.FindPlayer(id); }

        std::string WeaponOf(RonComp::Side side) const
        {
            return Match.GetFaction(side) == RonComp::Faction::Swat ? "m4a1" : "akm";
        }

        void GoLive() { Match.Tick(Settings.Get("mp_freezetime")); }

        // Kills every living player on `side`, each by the first living player of the other side.
        void KillAll(RonComp::Side side)
        {
            const RonComp::Side killerSide = RonComp::Opposite(side);
            for (;;)
            {
                const RonComp::PlayerId victim = FirstAlive(side);
                if (victim == RonComp::InvalidPlayer) break;
                const RonComp::PlayerId killer = FirstAlive(killerSide);
                Match.OnKill(killer, victim, WeaponOf(killerSide), false);
                if (Match.FindPlayer(victim)->Alive) break; // kill was ignored: avoid looping forever
            }
        }

        // From FreezeTime: plays one round won by `winner` by elimination, then advances through the
        // round-end delay (and halftime, if any) so the match sits at the next FreezeTime or MatchEnd.
        void PlayRound(RonComp::Side winner)
        {
            GoLive();
            KillAll(RonComp::Opposite(winner));
            FinishRoundEnd();
        }

        void FinishRoundEnd()
        {
            Match.Tick(Settings.Get("mp_round_restart_delay"));
            if (Match.GetPhase() == RonComp::Phase::Halftime)
            {
                Match.Tick(Settings.Get("mp_halftime_duration"));
            }
        }

        // Plays one round won by `team` (not side) by elimination.
        void TeamWinsRound(int team) { PlayRound(Match.GetSide(team)); }

        int CountEvents(const std::vector<RonComp::Event>& events, RonComp::EventType type) const
        {
            int count = 0;
            for (const RonComp::Event& event : events)
            {
                if (event.Type == type) ++count;
            }
            return count;
        }
    };
}
