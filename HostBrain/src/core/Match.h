#pragma once

// The competitive match: round phases, score, side swaps, overtime, economy, buying and stats.
//
// Adapters feed game facts in (kills, damage, plants, purchases, joins) and drain Events out to
// apply them in the game (respawns, money, items, replicated HUD state). The match never touches
// the game itself, which keeps every rule unit-testable.

#include "Items.h"
#include "Settings.h"
#include "Types.h"

#include <cstdint>
#include <map>
#include <random>
#include <string>
#include <utility>
#include <vector>

namespace RonComp
{
    struct PlayerStats
    {
        int Kills = 0;
        int Deaths = 0;
        int Assists = 0;
        int Headshots = 0;
        int Damage = 0;
        int Mvps = 0;
    };

    struct PlayerState
    {
        PlayerId Id = InvalidPlayer;
        int Team = NoTeam; // NoTeam = spectator
        bool IsBot = false;
        bool Alive = false;
        int Money = 0;
        PlayerStats Stats;
        int RoundKills = 0;
        int RoundDamage = 0;
    };

    struct RoundRecord
    {
        int Round = 0;
        int WinnerTeam = NoTeam;
        Side WinnerSide = Side::Defenders;
        RoundEndReason Reason = RoundEndReason::None;
        PlayerId Mvp = InvalidPlayer;
    };

    enum class EventType : std::uint8_t
    {
        PhaseChanged,  // NewPhase, Seconds = phase duration
        RoundStarted,  // Value = round number (0 in warmup), ResetInventory: strip gear before respawning
        RoundEnded,    // Team = winner, Reason, Player = MVP, Value = round number
        MoneyChanged,  // Player, Value = new balance, Amount = delta
        GiveBomb,      // Player
        ItemPurchased, // Player, Item = item id, Amount = price
        SidesSwapped,
        MatchEnded,    // Team = winner (NoTeam = draw)
        Respawn,       // Player (warmup deaths and late joiners)
        Kill,          // Player = killer, Other = victim, Item = weapon id, Headshot, Value = reward
        BombPlanted,   // Player, Value = site
        BombDefused,   // Player
        BombExploded,
        Paused,
        Unpaused,
    };

    struct Event
    {
        EventType Type = EventType::PhaseChanged;
        Phase NewPhase = Phase::Idle;
        PlayerId Player = InvalidPlayer;
        PlayerId Other = InvalidPlayer;
        int Team = NoTeam;
        int Amount = 0;
        int Value = 0;
        double Seconds = 0.0;
        RoundEndReason Reason = RoundEndReason::None;
        bool ResetInventory = false;
        bool Headshot = false;
        std::string Item;
    };

    // What the player currently carries, as reported by the inventory adapter at purchase time.
    struct InventorySnapshot
    {
        std::map<std::string, int> Counts; // item id -> count
        int Grenades = 0;

        int CountOf(const std::string& itemId) const
        {
            const auto it = Counts.find(itemId);
            return it == Counts.end() ? 0 : it->second;
        }
    };

    enum class BuyResult : std::uint8_t
    {
        Ok,
        NotPlaying,
        Dead,
        BuyTimeOver,
        NotInBuyZone,
        UnknownItem,
        WrongTeam,
        CarryLimit,
        GrenadeLimit,
        NotEnoughMoney,
    };

    const char* ToString(BuyResult result);
    const char* ToString(EventType type);

    class Match
    {
    public:
        // Settings are read live, so host commands (comp_set) take effect from the next use.
        Match(const Settings& settings, const ItemCatalog& items, std::uint32_t seed = 1);

        // Roster
        bool AddPlayer(PlayerId id, int team, bool isBot = false);
        bool RemovePlayer(PlayerId id);
        bool ChangeTeam(PlayerId id, int team);

        // Flow
        void StartWarmup();
        void StartMatch();
        void Tick(double deltaSeconds);
        void RequestPause(); // takes effect now during freeze time, otherwise at the next freeze time
        void Unpause();

        // Game facts
        void OnDamage(PlayerId attacker, PlayerId victim, int amount);
        void OnKill(PlayerId killer, PlayerId victim, const std::string& weaponItemId, bool headshot);
        bool OnBombPlanted(PlayerId planter, int site);
        bool OnBombDefused(PlayerId defuser);
        void OnBombCarrierChanged(PlayerId carrier); // InvalidPlayer = dropped
        BuyResult TryBuy(PlayerId id, const std::string& itemId, bool inBuyZone, const InventorySnapshot& inventory);

        // Queries
        Phase GetPhase() const { return m_Phase; }
        double GetPhaseTimeLeft() const { return m_PhaseTimeLeft; }
        bool IsPaused() const { return m_Paused; }
        bool IsPausePending() const { return m_PausePending; }
        int GetRoundNumber() const;
        int GetRoundsPlayed() const { return static_cast<int>(m_History.size()); }
        int GetScore(int team) const;
        Side GetSide(int team) const;
        int GetTeamOnSide(Side side) const;
        Faction GetFaction(Side side) const;
        bool IsOvertime() const { return m_OvertimeIndex > 0; }
        int GetOvertimeIndex() const { return m_OvertimeIndex; }
        int GetWinner() const { return m_Winner; }
        int GetLossCounter(int team) const;
        bool IsBombPlanted() const { return m_BombPlanted; }
        int GetBombSite() const { return m_BombSite; }
        PlayerId GetBombCarrier() const { return m_BombCarrier; }
        bool IsBuyWindowOpen() const;
        bool CanBuy(PlayerId id) const;
        const PlayerState* FindPlayer(PlayerId id) const;
        const std::vector<PlayerState>& GetPlayers() const { return m_Players; }
        const std::vector<RoundRecord>& GetHistory() const { return m_History; }

        std::vector<Event> DrainEvents();

    private:
        PlayerState* Find(PlayerId id);
        bool InRound() const { return m_Phase == Phase::Live || m_Phase == Phase::BombPlanted; }
        bool CountsForStats() const { return InRound() || m_Phase == Phase::RoundEnd; }

        void SetPhase(Phase phase, double duration);
        void OnPhaseTimerExpired();
        void BeginRound(bool newHalf);
        void EndRound(Side winner, RoundEndReason reason, PlayerId mvpOverride);
        void AdvanceAfterRound();
        void EndMatch(int winnerTeam);
        void CheckElimination();
        void PickBombCarrier();
        void AddMoney(PlayerState& player, int delta);
        PlayerId PickMvp(int winnerTeam, PlayerId mvpOverride) const;

        int HalfStartMoney() const;
        int SegmentStart(int overtimeIndex) const; // rounds played before the segment begins
        int SegmentEnd(int overtimeIndex) const;   // rounds played when the segment is over
        int SegmentHalf(int overtimeIndex) const;  // rounds per half within the segment
        int ClinchTarget(int overtimeIndex) const;

        int AliveOnSide(Side side) const;
        int PlayersOnSide(Side side) const;
        bool SideCanAccess(ItemAccess access, Side side) const;

        void Emit(const Event& event) { m_Events.push_back(event); }

        const Settings& m_Settings;
        const ItemCatalog& m_Items;
        std::mt19937 m_Rng;

        std::vector<PlayerState> m_Players;
        std::vector<RoundRecord> m_History;
        std::vector<Event> m_Events;

        Phase m_Phase = Phase::Idle;
        double m_PhaseTimeLeft = 0.0;
        double m_LiveElapsed = 0.0;
        bool m_Paused = false;
        bool m_PausePending = false;

        int m_Score[TeamCount] = {0, 0};
        int m_LossCounter[TeamCount] = {0, 0};
        Side m_TeamSide[TeamCount] = {Side::Attackers, Side::Defenders};
        int m_OvertimeIndex = 0;
        int m_Winner = NoTeam;

        bool m_BombPlanted = false;
        int m_BombSite = -1;
        PlayerId m_BombCarrier = InvalidPlayer;
        PlayerId m_Planter = InvalidPlayer;

        int m_SidePlayersAtRoundStart[TeamCount] = {0, 0}; // indexed by Side
        std::map<std::pair<PlayerId, PlayerId>, int> m_RoundDamage; // (attacker, victim) -> damage
        std::map<PlayerId, int> m_DamageTaken;                       // victim -> damage this round
    };
}
