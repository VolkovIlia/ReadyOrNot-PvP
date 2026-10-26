#include "Match.h"

#include <algorithm>

namespace RonComp
{
    const char* ToString(BuyResult result)
    {
        switch (result)
        {
        case BuyResult::Ok: return "Ok";
        case BuyResult::NotPlaying: return "NotPlaying";
        case BuyResult::Dead: return "Dead";
        case BuyResult::BuyTimeOver: return "BuyTimeOver";
        case BuyResult::NotInBuyZone: return "NotInBuyZone";
        case BuyResult::UnknownItem: return "UnknownItem";
        case BuyResult::WrongTeam: return "WrongTeam";
        case BuyResult::CarryLimit: return "CarryLimit";
        case BuyResult::GrenadeLimit: return "GrenadeLimit";
        case BuyResult::NotEnoughMoney: return "NotEnoughMoney";
        }
        return "?";
    }

    const char* ToString(EventType type)
    {
        switch (type)
        {
        case EventType::PhaseChanged: return "PhaseChanged";
        case EventType::RoundStarted: return "RoundStarted";
        case EventType::RoundEnded: return "RoundEnded";
        case EventType::MoneyChanged: return "MoneyChanged";
        case EventType::GiveBomb: return "GiveBomb";
        case EventType::ItemPurchased: return "ItemPurchased";
        case EventType::SidesSwapped: return "SidesSwapped";
        case EventType::MatchEnded: return "MatchEnded";
        case EventType::Respawn: return "Respawn";
        case EventType::Kill: return "Kill";
        case EventType::BombPlanted: return "BombPlanted";
        case EventType::BombDefused: return "BombDefused";
        case EventType::BombExploded: return "BombExploded";
        case EventType::Paused: return "Paused";
        case EventType::Unpaused: return "Unpaused";
        }
        return "?";
    }

    Match::Match(const Settings& settings, const ItemCatalog& items, std::uint32_t seed)
        : m_Settings(settings), m_Items(items), m_Rng(seed)
    {
    }

    // ---------------------------------------------------------------- roster

    bool Match::AddPlayer(PlayerId id, int team, bool isBot)
    {
        if (id == InvalidPlayer || Find(id) || team < NoTeam || team >= TeamCount)
        {
            return false;
        }

        PlayerState player;
        player.Id = id;
        player.Team = team;
        player.IsBot = isBot;
        player.Money = m_Phase == Phase::Warmup ? m_Settings.GetInt("mp_warmup_money") : HalfStartMoney();

        // Joining before the round goes live spawns you; joining mid-round waits for the next one.
        const bool spawnNow = team != NoTeam && (m_Phase == Phase::Warmup || m_Phase == Phase::FreezeTime);
        player.Alive = spawnNow;
        m_Players.push_back(player);

        if (spawnNow)
        {
            if (m_Phase == Phase::FreezeTime)
            {
                ++m_SidePlayersAtRoundStart[static_cast<int>(GetSide(team))];
            }
            Event event;
            event.Type = EventType::Respawn;
            event.Player = id;
            Emit(event);
        }
        return true;
    }

    bool Match::RemovePlayer(PlayerId id)
    {
        const auto it = std::find_if(m_Players.begin(), m_Players.end(), [&](const PlayerState& p) { return p.Id == id; });
        if (it == m_Players.end())
        {
            return false;
        }
        m_Players.erase(it);
        if (m_BombCarrier == id)
        {
            m_BombCarrier = InvalidPlayer;
        }
        if (m_Phase == Phase::Live)
        {
            CheckElimination();
        }
        return true;
    }

    bool Match::ChangeTeam(PlayerId id, int team)
    {
        PlayerState* player = Find(id);
        if (!player || team < NoTeam || team >= TeamCount)
        {
            return false;
        }
        if (player->Team == team)
        {
            return true;
        }
        player->Team = team;
        player->Alive = team != NoTeam && (m_Phase == Phase::Warmup || m_Phase == Phase::FreezeTime);
        if (m_BombCarrier == id)
        {
            m_BombCarrier = InvalidPlayer;
        }
        if (player->Alive)
        {
            Event event;
            event.Type = EventType::Respawn;
            event.Player = id;
            Emit(event);
        }
        if (m_Phase == Phase::Live)
        {
            CheckElimination();
        }
        return true;
    }

    // ---------------------------------------------------------------- flow

    void Match::StartWarmup()
    {
        m_History.clear();
        m_Score[0] = m_Score[1] = 0;
        m_Winner = NoTeam;
        m_OvertimeIndex = 0;
        m_Paused = m_PausePending = false;

        const int money = m_Settings.GetInt("mp_warmup_money");
        for (PlayerState& player : m_Players)
        {
            player.Alive = player.Team != NoTeam;
            AddMoney(player, money - player.Money);
        }

        Event started;
        started.Type = EventType::RoundStarted;
        started.Value = 0;
        started.ResetInventory = true;
        Emit(started);

        SetPhase(Phase::Warmup, m_Settings.Get("mp_warmuptime"));
    }

    void Match::StartMatch()
    {
        m_History.clear();
        m_Score[0] = m_Score[1] = 0;
        m_Winner = NoTeam;
        m_OvertimeIndex = 0;
        m_Paused = m_PausePending = false;

        const bool team0Attacks = m_Settings.GetBool("mp_team0_starts_attacking");
        m_TeamSide[0] = team0Attacks ? Side::Attackers : Side::Defenders;
        m_TeamSide[1] = Opposite(m_TeamSide[0]);

        for (PlayerState& player : m_Players)
        {
            player.Stats = PlayerStats{};
        }

        BeginRound(true);
    }

    void Match::Tick(double deltaSeconds)
    {
        double remaining = std::max(0.0, deltaSeconds);

        // Each iteration either consumes time or performs one phase transition. Zero-length phases
        // (e.g. mp_halftime_duration 0) fall through immediately; the guard stops a misconfigured loop.
        for (int guard = 0; guard < 64; ++guard)
        {
            const bool timed = m_Phase != Phase::Idle && m_Phase != Phase::MatchEnd;
            if (!timed || m_Paused)
            {
                return;
            }
            if (m_PhaseTimeLeft > 0.0)
            {
                if (remaining <= 0.0)
                {
                    return;
                }
                const double step = std::min(remaining, m_PhaseTimeLeft);
                m_PhaseTimeLeft -= step;
                remaining -= step;
                if (m_Phase == Phase::Live)
                {
                    m_LiveElapsed += step;
                }
                if (m_PhaseTimeLeft > 0.0)
                {
                    return;
                }
            }
            OnPhaseTimerExpired();
        }
    }

    void Match::RequestPause()
    {
        if (m_Paused)
        {
            return;
        }
        if (m_Phase == Phase::FreezeTime)
        {
            m_Paused = true;
            m_PausePending = false;
            Event event;
            event.Type = EventType::Paused;
            Emit(event);
        }
        else
        {
            m_PausePending = true;
        }
    }

    void Match::Unpause()
    {
        const bool wasPaused = m_Paused;
        m_Paused = false;
        m_PausePending = false;
        if (wasPaused)
        {
            Event event;
            event.Type = EventType::Unpaused;
            Emit(event);
        }
    }

    void Match::SetPhase(Phase phase, double duration)
    {
        m_Phase = phase;
        m_PhaseTimeLeft = std::max(0.0, duration);

        Event event;
        event.Type = EventType::PhaseChanged;
        event.NewPhase = phase;
        event.Seconds = m_PhaseTimeLeft;
        Emit(event);
    }

    void Match::OnPhaseTimerExpired()
    {
        switch (m_Phase)
        {
        case Phase::Warmup:
            StartMatch();
            break;
        case Phase::FreezeTime:
            m_LiveElapsed = 0.0;
            SetPhase(Phase::Live, m_Settings.Get("mp_roundtime") * 60.0);
            CheckElimination(); // a side may have emptied during freeze time
            break;
        case Phase::Live:
            EndRound(Side::Defenders, RoundEndReason::TimeExpired, InvalidPlayer);
            break;
        case Phase::BombPlanted:
        {
            Event exploded;
            exploded.Type = EventType::BombExploded;
            exploded.Value = m_BombSite;
            Emit(exploded);
            EndRound(Side::Attackers, RoundEndReason::BombExploded, m_Planter);
            break;
        }
        case Phase::RoundEnd:
            AdvanceAfterRound();
            break;
        case Phase::Halftime:
            BeginRound(true);
            break;
        case Phase::Idle:
        case Phase::MatchEnd:
            break;
        }
    }

    void Match::BeginRound(bool newHalf)
    {
        if (newHalf)
        {
            const int money = HalfStartMoney();
            for (PlayerState& player : m_Players)
            {
                AddMoney(player, money - player.Money);
            }
            const int startingLosses = m_Settings.GetInt("mp_starting_losses");
            m_LossCounter[0] = m_LossCounter[1] = startingLosses;
        }

        for (PlayerState& player : m_Players)
        {
            player.Alive = player.Team != NoTeam;
            player.RoundKills = 0;
            player.RoundDamage = 0;
        }
        m_RoundDamage.clear();
        m_DamageTaken.clear();
        m_BombPlanted = false;
        m_BombSite = -1;
        m_BombCarrier = InvalidPlayer;
        m_Planter = InvalidPlayer;
        m_LiveElapsed = 0.0;
        m_SidePlayersAtRoundStart[static_cast<int>(Side::Attackers)] = PlayersOnSide(Side::Attackers);
        m_SidePlayersAtRoundStart[static_cast<int>(Side::Defenders)] = PlayersOnSide(Side::Defenders);

        Event started;
        started.Type = EventType::RoundStarted;
        started.Value = GetRoundsPlayed() + 1;
        started.ResetInventory = newHalf;
        Emit(started);

        SetPhase(Phase::FreezeTime, m_Settings.Get("mp_freezetime"));
        PickBombCarrier();

        if (m_PausePending)
        {
            RequestPause();
        }
    }

    void Match::EndRound(Side winnerSide, RoundEndReason reason, PlayerId mvpOverride)
    {
        const int roundNumber = GetRoundsPlayed() + 1;
        const int winnerTeam = GetTeamOnSide(winnerSide);
        const int loserTeam = OtherTeam(winnerTeam);
        const Side loserSide = Opposite(winnerSide);
        ++m_Score[winnerTeam];

        // Winners
        int winReward = 0;
        switch (reason)
        {
        case RoundEndReason::AttackersEliminated:
        case RoundEndReason::DefendersEliminated:
            winReward = m_Settings.GetInt("cash_team_elimination");
            break;
        case RoundEndReason::TimeExpired:
            winReward = m_Settings.GetInt("cash_team_win_by_time");
            break;
        case RoundEndReason::BombExploded:
            winReward = m_Settings.GetInt("cash_team_attackers_win_bomb");
            break;
        case RoundEndReason::BombDefused:
            winReward = m_Settings.GetInt("cash_team_defenders_win_defuse");
            break;
        case RoundEndReason::None:
            break;
        }
        for (PlayerState& player : m_Players)
        {
            if (player.Team == winnerTeam)
            {
                AddMoney(player, winReward);
            }
        }

        // Losers: the counter rises first, so a team starting a half at 1 loss earns step 2 ($1,900).
        const int maxLosses = m_Settings.GetInt("mp_loss_bonus_max_losses");
        m_LossCounter[loserTeam] = std::min(m_LossCounter[loserTeam] + 1, maxLosses);
        const int lossBonus = m_Settings.GetInt("cash_team_loser_bonus")
            + m_Settings.GetInt("cash_team_loser_bonus_step") * std::max(0, m_LossCounter[loserTeam] - 1);
        const int plantedExtra = loserSide == Side::Attackers && m_BombPlanted
            ? m_Settings.GetInt("cash_team_planted_bomb_but_lost")
            : 0;
        const bool survivorsForfeit = reason == RoundEndReason::TimeExpired && loserSide == Side::Attackers
            && m_Settings.GetBool("mp_attackers_survivor_no_bonus");
        for (PlayerState& player : m_Players)
        {
            if (player.Team != loserTeam || (survivorsForfeit && player.Alive))
            {
                continue;
            }
            AddMoney(player, lossBonus + plantedExtra);
        }

        if (m_Settings.GetBool("mp_loss_bonus_decrement_on_win"))
        {
            m_LossCounter[winnerTeam] = std::max(0, m_LossCounter[winnerTeam] - 1);
        }
        else
        {
            m_LossCounter[winnerTeam] = 0;
        }

        const PlayerId mvp = PickMvp(winnerTeam, mvpOverride);
        if (PlayerState* mvpPlayer = Find(mvp))
        {
            ++mvpPlayer->Stats.Mvps;
        }

        RoundRecord record;
        record.Round = roundNumber;
        record.WinnerTeam = winnerTeam;
        record.WinnerSide = winnerSide;
        record.Reason = reason;
        record.Mvp = mvp;
        m_History.push_back(record);

        Event ended;
        ended.Type = EventType::RoundEnded;
        ended.Team = winnerTeam;
        ended.Reason = reason;
        ended.Player = mvp;
        ended.Value = roundNumber;
        Emit(ended);

        SetPhase(Phase::RoundEnd, m_Settings.Get("mp_round_restart_delay"));
    }

    void Match::AdvanceAfterRound()
    {
        const int played = GetRoundsPlayed();
        const int k = m_OvertimeIndex;
        const int leader = m_Score[0] >= m_Score[1] ? 0 : 1;
        const int leaderScore = m_Score[leader];

        if (m_Settings.GetBool("mp_match_can_clinch") && leaderScore >= ClinchTarget(k))
        {
            EndMatch(leader);
            return;
        }

        if (played >= SegmentEnd(k))
        {
            if (m_Score[0] != m_Score[1])
            {
                EndMatch(leader);
            }
            else if (m_Settings.GetBool("mp_overtime_enable"))
            {
                // Overtime keeps the sides of the half that just ended; only the money resets.
                ++m_OvertimeIndex;
                BeginRound(true);
            }
            else
            {
                EndMatch(NoTeam);
            }
            return;
        }

        if (played == SegmentStart(k) + SegmentHalf(k))
        {
            std::swap(m_TeamSide[0], m_TeamSide[1]);
            Event swapped;
            swapped.Type = EventType::SidesSwapped;
            Emit(swapped);
            SetPhase(Phase::Halftime, m_Settings.Get("mp_halftime_duration"));
            return;
        }

        BeginRound(false);
    }

    void Match::EndMatch(int winnerTeam)
    {
        m_Winner = winnerTeam;
        Event ended;
        ended.Type = EventType::MatchEnded;
        ended.Team = winnerTeam;
        Emit(ended);
        SetPhase(Phase::MatchEnd, 0.0);
    }

    void Match::CheckElimination()
    {
        // After the plant only the bomb decides the round, as in CS.
        if (m_Phase != Phase::Live)
        {
            return;
        }
        const int attackersAtStart = m_SidePlayersAtRoundStart[static_cast<int>(Side::Attackers)];
        const int defendersAtStart = m_SidePlayersAtRoundStart[static_cast<int>(Side::Defenders)];
        if (attackersAtStart > 0 && AliveOnSide(Side::Attackers) == 0)
        {
            EndRound(Side::Defenders, RoundEndReason::AttackersEliminated, InvalidPlayer);
        }
        else if (defendersAtStart > 0 && AliveOnSide(Side::Defenders) == 0)
        {
            EndRound(Side::Attackers, RoundEndReason::DefendersEliminated, InvalidPlayer);
        }
    }

    void Match::PickBombCarrier()
    {
        std::vector<PlayerId> candidates;
        for (const PlayerState& player : m_Players)
        {
            if (player.Alive && player.Team != NoTeam && GetSide(player.Team) == Side::Attackers)
            {
                candidates.push_back(player.Id);
            }
        }
        if (candidates.empty())
        {
            return;
        }
        std::sort(candidates.begin(), candidates.end()); // deterministic for a given seed
        std::uniform_int_distribution<std::size_t> pick(0, candidates.size() - 1);
        m_BombCarrier = candidates[pick(m_Rng)];

        Event event;
        event.Type = EventType::GiveBomb;
        event.Player = m_BombCarrier;
        Emit(event);
    }

    PlayerId Match::PickMvp(int winnerTeam, PlayerId mvpOverride) const
    {
        if (mvpOverride != InvalidPlayer && FindPlayer(mvpOverride))
        {
            return mvpOverride;
        }
        const PlayerState* best = nullptr;
        for (const PlayerState& player : m_Players)
        {
            if (player.Team != winnerTeam || player.RoundKills == 0)
            {
                continue;
            }
            if (!best || player.RoundKills > best->RoundKills
                || (player.RoundKills == best->RoundKills && player.RoundDamage > best->RoundDamage))
            {
                best = &player;
            }
        }
        return best ? best->Id : InvalidPlayer;
    }

    void Match::AddMoney(PlayerState& player, int delta)
    {
        const int before = player.Money;
        player.Money = std::max(0, std::min(player.Money + delta, m_Settings.GetInt("mp_maxmoney")));
        if (player.Money == before)
        {
            return;
        }
        Event event;
        event.Type = EventType::MoneyChanged;
        event.Player = player.Id;
        event.Value = player.Money;
        event.Amount = player.Money - before;
        Emit(event);
    }

    // ---------------------------------------------------------------- game facts

    void Match::OnDamage(PlayerId attacker, PlayerId victim, int amount)
    {
        if (!CountsForStats() || amount <= 0 || attacker == victim)
        {
            return;
        }
        PlayerState* attackerState = Find(attacker);
        const PlayerState* victimState = FindPlayer(victim);
        if (!attackerState || !victimState || attackerState->Team == victimState->Team)
        {
            return;
        }

        // Like CS, damage past the victim's remaining health does not count toward stats.
        int& taken = m_DamageTaken[victim];
        const int counted = std::min(amount, std::max(0, m_Settings.GetInt("mp_damage_cap_per_victim") - taken));
        if (counted <= 0)
        {
            return;
        }
        taken += counted;
        m_RoundDamage[{attacker, victim}] += counted;
        attackerState->Stats.Damage += counted;
        attackerState->RoundDamage += counted;
    }

    void Match::OnKill(PlayerId killer, PlayerId victim, const std::string& weaponItemId, bool headshot)
    {
        PlayerState* victimState = Find(victim);
        if (!victimState)
        {
            return;
        }

        Event kill;
        kill.Type = EventType::Kill;
        kill.Player = killer;
        kill.Other = victim;
        kill.Item = weaponItemId;
        kill.Headshot = headshot;

        if (m_Phase == Phase::Warmup)
        {
            Emit(kill);
            AddMoney(*victimState, m_Settings.GetInt("mp_warmup_money") - victimState->Money);
            Event respawn;
            respawn.Type = EventType::Respawn;
            respawn.Player = victim;
            Emit(respawn);
            return;
        }

        if (!CountsForStats() || !victimState->Alive)
        {
            return; // freeze time, halftime, or a duplicate death report
        }

        victimState->Alive = false;
        ++victimState->Stats.Deaths;
        if (m_BombCarrier == victim)
        {
            m_BombCarrier = InvalidPlayer;
        }

        PlayerState* killerState = killer == victim ? nullptr : Find(killer);
        if (killerState && killerState->Team == victimState->Team)
        {
            AddMoney(*killerState, m_Settings.GetInt("cash_player_killed_teammate"));
        }
        else if (killerState)
        {
            ++killerState->Stats.Kills;
            ++killerState->RoundKills;
            if (headshot)
            {
                ++killerState->Stats.Headshots;
            }
            const Item* weapon = m_Items.Find(weaponItemId);
            const int reward = weapon ? weapon->KillReward : m_Settings.GetInt("cash_player_killed_enemy_default");
            AddMoney(*killerState, reward);
            kill.Value = reward;

            const int teamBonus = m_Settings.GetInt("cash_team_defenders_per_kill");
            if (teamBonus != 0 && GetSide(killerState->Team) == Side::Defenders)
            {
                const int team = killerState->Team;
                for (PlayerState& player : m_Players)
                {
                    if (player.Team == team)
                    {
                        AddMoney(player, teamBonus);
                    }
                }
            }
        }

        const int threshold = m_Settings.GetInt("mp_assist_damage_threshold");
        for (const auto& entry : m_RoundDamage)
        {
            const PlayerId assister = entry.first.first;
            if (entry.first.second != victim || assister == killer || entry.second < threshold)
            {
                continue;
            }
            PlayerState* assisterState = Find(assister);
            if (assisterState && assisterState->Team != victimState->Team)
            {
                ++assisterState->Stats.Assists;
            }
        }

        Emit(kill);
        CheckElimination();
    }

    bool Match::OnBombPlanted(PlayerId planter, int site)
    {
        PlayerState* player = Find(planter);
        if (m_Phase != Phase::Live || !player || !player->Alive || player->Team == NoTeam
            || GetSide(player->Team) != Side::Attackers)
        {
            return false;
        }

        m_BombPlanted = true;
        m_BombSite = site;
        m_Planter = planter;
        m_BombCarrier = InvalidPlayer;
        AddMoney(*player, m_Settings.GetInt("cash_player_bomb_planted"));

        Event planted;
        planted.Type = EventType::BombPlanted;
        planted.Player = planter;
        planted.Value = site;
        Emit(planted);

        SetPhase(Phase::BombPlanted, m_Settings.Get("mp_c4timer"));
        return true;
    }

    bool Match::OnBombDefused(PlayerId defuser)
    {
        PlayerState* player = Find(defuser);
        if (m_Phase != Phase::BombPlanted || !player || !player->Alive || player->Team == NoTeam
            || GetSide(player->Team) != Side::Defenders)
        {
            return false;
        }

        AddMoney(*player, m_Settings.GetInt("cash_player_bomb_defused"));

        Event defused;
        defused.Type = EventType::BombDefused;
        defused.Player = defuser;
        Emit(defused);

        EndRound(Side::Defenders, RoundEndReason::BombDefused, defuser);
        return true;
    }

    void Match::OnBombCarrierChanged(PlayerId carrier)
    {
        if (carrier == InvalidPlayer)
        {
            m_BombCarrier = InvalidPlayer;
            return;
        }
        const PlayerState* player = FindPlayer(carrier);
        if (player && player->Alive && player->Team != NoTeam && GetSide(player->Team) == Side::Attackers)
        {
            m_BombCarrier = carrier;
        }
    }

    BuyResult Match::TryBuy(PlayerId id, const std::string& itemId, bool inBuyZone, const InventorySnapshot& inventory)
    {
        PlayerState* player = Find(id);
        if (!player || player->Team == NoTeam)
        {
            return BuyResult::NotPlaying;
        }
        if (!player->Alive)
        {
            return BuyResult::Dead;
        }
        if (!IsBuyWindowOpen())
        {
            return BuyResult::BuyTimeOver;
        }
        if (!inBuyZone)
        {
            return BuyResult::NotInBuyZone;
        }
        const Item* item = m_Items.Find(itemId);
        if (!item)
        {
            return BuyResult::UnknownItem;
        }
        if (!SideCanAccess(item->Access, GetSide(player->Team)))
        {
            return BuyResult::WrongTeam;
        }
        if (inventory.CountOf(itemId) >= item->MaxCarry)
        {
            return BuyResult::CarryLimit;
        }
        if (item->Category == ItemCategory::Grenade && inventory.Grenades >= m_Settings.GetInt("mp_max_grenades"))
        {
            return BuyResult::GrenadeLimit;
        }
        if (player->Money < item->Price)
        {
            return BuyResult::NotEnoughMoney;
        }

        AddMoney(*player, -item->Price);
        Event purchased;
        purchased.Type = EventType::ItemPurchased;
        purchased.Player = id;
        purchased.Item = item->Id;
        purchased.Amount = item->Price;
        Emit(purchased);
        return BuyResult::Ok;
    }

    // ---------------------------------------------------------------- queries

    int Match::GetRoundNumber() const
    {
        switch (m_Phase)
        {
        case Phase::FreezeTime:
        case Phase::Live:
        case Phase::BombPlanted:
            return GetRoundsPlayed() + 1;
        default:
            return GetRoundsPlayed();
        }
    }

    int Match::GetScore(int team) const
    {
        return team >= 0 && team < TeamCount ? m_Score[team] : 0;
    }

    Side Match::GetSide(int team) const
    {
        return team >= 0 && team < TeamCount ? m_TeamSide[team] : Side::Defenders;
    }

    int Match::GetTeamOnSide(Side side) const
    {
        return m_TeamSide[0] == side ? 0 : 1;
    }

    Faction Match::GetFaction(Side side) const
    {
        const bool suspectsAttack = m_Settings.GetInt("mp_attackers_faction") == 0;
        const bool attackers = side == Side::Attackers;
        return attackers == suspectsAttack ? Faction::Suspects : Faction::Swat;
    }

    int Match::GetLossCounter(int team) const
    {
        return team >= 0 && team < TeamCount ? m_LossCounter[team] : 0;
    }

    bool Match::IsBuyWindowOpen() const
    {
        return m_Phase == Phase::Warmup || m_Phase == Phase::FreezeTime
            || (m_Phase == Phase::Live && m_LiveElapsed < m_Settings.Get("mp_buytime"));
    }

    bool Match::CanBuy(PlayerId id) const
    {
        const PlayerState* player = FindPlayer(id);
        return player && player->Team != NoTeam && player->Alive && IsBuyWindowOpen();
    }

    const PlayerState* Match::FindPlayer(PlayerId id) const
    {
        const auto it = std::find_if(m_Players.begin(), m_Players.end(), [&](const PlayerState& p) { return p.Id == id; });
        return it == m_Players.end() ? nullptr : &*it;
    }

    PlayerState* Match::Find(PlayerId id)
    {
        return const_cast<PlayerState*>(static_cast<const Match*>(this)->FindPlayer(id));
    }

    std::vector<Event> Match::DrainEvents()
    {
        std::vector<Event> events;
        events.swap(m_Events);
        return events;
    }

    // ---------------------------------------------------------------- helpers

    int Match::HalfStartMoney() const
    {
        return m_OvertimeIndex > 0 ? m_Settings.GetInt("mp_overtime_startmoney") : m_Settings.GetInt("mp_startmoney");
    }

    int Match::SegmentStart(int overtimeIndex) const
    {
        return overtimeIndex == 0 ? 0 : m_Settings.GetInt("mp_maxrounds") + (overtimeIndex - 1) * m_Settings.GetInt("mp_overtime_maxrounds");
    }

    int Match::SegmentEnd(int overtimeIndex) const
    {
        return m_Settings.GetInt("mp_maxrounds") + overtimeIndex * m_Settings.GetInt("mp_overtime_maxrounds");
    }

    int Match::SegmentHalf(int overtimeIndex) const
    {
        return (overtimeIndex == 0 ? m_Settings.GetInt("mp_maxrounds") : m_Settings.GetInt("mp_overtime_maxrounds")) / 2;
    }

    int Match::ClinchTarget(int overtimeIndex) const
    {
        // Regulation 24: 13. Each overtime adds half its length: 16, 19, 22...
        return SegmentHalf(0) + overtimeIndex * (m_Settings.GetInt("mp_overtime_maxrounds") / 2) + 1;
    }

    int Match::AliveOnSide(Side side) const
    {
        return static_cast<int>(std::count_if(m_Players.begin(), m_Players.end(), [&](const PlayerState& p) {
            return p.Alive && p.Team != NoTeam && GetSide(p.Team) == side;
        }));
    }

    int Match::PlayersOnSide(Side side) const
    {
        return static_cast<int>(std::count_if(m_Players.begin(), m_Players.end(), [&](const PlayerState& p) {
            return p.Team != NoTeam && GetSide(p.Team) == side;
        }));
    }

    bool Match::SideCanAccess(ItemAccess access, Side side) const
    {
        switch (access)
        {
        case ItemAccess::Any: return true;
        case ItemAccess::Attackers: return side == Side::Attackers;
        case ItemAccess::Defenders: return side == Side::Defenders;
        case ItemAccess::Swat: return GetFaction(side) == Faction::Swat;
        case ItemAccess::Suspects: return GetFaction(side) == Faction::Suspects;
        }
        return false;
    }
}
