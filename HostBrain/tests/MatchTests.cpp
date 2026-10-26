#include "TestHelpers.h"

using namespace RonComp;
using TestHelpers::Fixture;

namespace
{
    int MoneyOf(const Fixture& f, PlayerId id) { return f.Player(id).Money; }
}

// ---------------------------------------------------------------- flow

TEST(Match_StartPutsRoundOneInFreezeTime)
{
    Fixture f;
    f.Match.StartMatch();
    CHECK_EQ(f.Match.GetPhase(), Phase::FreezeTime);
    CHECK_EQ(f.Match.GetRoundNumber(), 1);
    CHECK_EQ(f.Match.GetPhaseTimeLeft(), 15.0);
    CHECK_EQ(f.Match.GetSide(0), Side::Attackers);
    CHECK_EQ(f.Match.GetSide(1), Side::Defenders);
    CHECK_EQ(f.Match.GetFaction(Side::Attackers), Faction::Suspects);
    CHECK_EQ(f.Match.GetLossCounter(0), 1);
    for (const PlayerState& player : f.Match.GetPlayers())
    {
        CHECK_EQ(player.Money, 800);
        CHECK(player.Alive);
    }

    const auto events = f.Match.DrainEvents();
    CHECK_EQ(f.CountEvents(events, EventType::RoundStarted), 1);
    CHECK_EQ(f.CountEvents(events, EventType::GiveBomb), 1);
    const PlayerId carrier = f.Match.GetBombCarrier();
    REQUIRE(carrier != InvalidPlayer);
    CHECK_EQ(f.Match.GetSide(f.Player(carrier).Team), Side::Attackers);
}

TEST(Match_FreezeTimeLeadsToLiveRound)
{
    Fixture f;
    f.Match.StartMatch();
    f.Match.Tick(14.9);
    CHECK_EQ(f.Match.GetPhase(), Phase::FreezeTime);
    f.Match.Tick(0.1);
    CHECK_EQ(f.Match.GetPhase(), Phase::Live);
    CHECK(f.Match.GetPhaseTimeLeft() > 115.1 && f.Match.GetPhaseTimeLeft() < 115.3);
}

TEST(Match_TimeExpiryGivesDefendersTheRound)
{
    Fixture f;
    f.Match.StartMatch();
    f.GoLive();
    // One attacker dies so we can see that only survivors forfeit the loss bonus.
    const PlayerId deadAttacker = f.FirstAlive(Side::Attackers);
    f.Match.OnKill(f.FirstAlive(Side::Defenders), deadAttacker, "m4a1", false);
    f.Match.Tick(200.0);

    REQUIRE(!f.Match.GetHistory().empty());
    const RoundRecord& round = f.Match.GetHistory().front();
    CHECK_EQ(round.Reason, RoundEndReason::TimeExpired);
    CHECK_EQ(round.WinnerSide, Side::Defenders);
    CHECK_EQ(f.Match.GetScore(1), 1);

    CHECK_EQ(MoneyOf(f, deadAttacker), 800 + 1900);
    CHECK_EQ(MoneyOf(f, 2), 800); // attacker who survived the clock gets nothing
    CHECK_EQ(MoneyOf(f, 7), 800 + 3250);
}

TEST(Match_EliminationEndsRoundAndPaysCs2Rewards)
{
    Fixture f;
    f.Match.StartMatch();
    f.GoLive();
    f.KillAll(Side::Attackers);

    CHECK_EQ(f.Match.GetPhase(), Phase::RoundEnd);
    CHECK_EQ(f.Match.GetHistory().back().Reason, RoundEndReason::AttackersEliminated);
    // Defender 6 got all five kills with an M4A1 ($300 each).
    CHECK_EQ(f.Player(6).Stats.Kills, 5);
    CHECK_EQ(MoneyOf(f, 6), 800 + 5 * 300 + 3250);
    CHECK_EQ(MoneyOf(f, 7), 800 + 3250);
    CHECK_EQ(MoneyOf(f, 1), 800 + 1900); // pistol-round loser gets the second ladder step
    CHECK_EQ(f.Match.GetHistory().back().Mvp, static_cast<PlayerId>(6));
}

TEST(Match_RoundEndDelayStartsNextRoundKeepingMoney)
{
    Fixture f;
    f.Match.StartMatch();
    f.PlayRound(Side::Defenders);
    CHECK_EQ(f.Match.GetPhase(), Phase::FreezeTime);
    CHECK_EQ(f.Match.GetRoundNumber(), 2);
    CHECK_EQ(MoneyOf(f, 7), 800 + 3250);
    for (const PlayerState& player : f.Match.GetPlayers())
    {
        CHECK(player.Alive);
    }
}

// ---------------------------------------------------------------- economy

TEST(Match_LossBonusLadderClimbsAndCaps)
{
    Fixture f;
    f.Settings.Set("mp_maxmoney", 100000); // keep the cap out of the way of the ladder arithmetic
    f.Match.StartMatch();
    const int expected[] = {1900, 2400, 2900, 3400, 3400};
    for (int bonus : expected)
    {
        const int before = MoneyOf(f, 2); // attacker 2 never gets kills
        f.PlayRound(Side::Defenders);
        CHECK_EQ(MoneyOf(f, 2) - before, bonus);
    }
    CHECK_EQ(f.Match.GetLossCounter(0), 5);

    f.PlayRound(Side::Attackers); // a win lowers the counter by one...
    CHECK_EQ(f.Match.GetLossCounter(0), 4);
    const int before = MoneyOf(f, 2);
    f.PlayRound(Side::Defenders); // ...so the next loss pays the top step again
    CHECK_EQ(MoneyOf(f, 2) - before, 3400);
}

TEST(Match_LossBonusResetsOnWinWhenConfigured)
{
    Fixture f;
    f.Settings.Set("mp_loss_bonus_decrement_on_win", 0);
    f.Match.StartMatch();
    f.PlayRound(Side::Defenders);
    f.PlayRound(Side::Defenders);
    f.PlayRound(Side::Attackers);
    CHECK_EQ(f.Match.GetLossCounter(0), 0);
    const int before = MoneyOf(f, 2);
    f.PlayRound(Side::Defenders);
    CHECK_EQ(MoneyOf(f, 2) - before, 1400);
}

TEST(Match_PistolWinnerLosingNextRoundGetsFirstStep)
{
    Fixture f;
    f.Match.StartMatch();
    f.PlayRound(Side::Attackers);
    const int before = MoneyOf(f, 2);
    f.PlayRound(Side::Defenders);
    CHECK_EQ(MoneyOf(f, 2) - before, 1400);
}

TEST(Match_KillRewardsDependOnWeapon)
{
    Fixture f;
    f.Match.StartMatch();
    f.GoLive();
    f.Match.OnKill(6, 1, "mp9", false);     // SMG: $600
    f.Match.OnKill(6, 2, "m24", true);      // AWP-like: $100
    f.Match.OnKill(6, 3, "unknown", false); // not in the catalog: default $300
    CHECK_EQ(MoneyOf(f, 6), 800 + 600 + 100 + 300);
    CHECK_EQ(f.Player(6).Stats.Headshots, 1);
    f.Match.OnKill(7, 1, "m4a1", false); // a second report of the same death is ignored
    CHECK_EQ(f.Player(7).Stats.Kills, 0);
    CHECK_EQ(f.Player(1).Stats.Deaths, 1);
    f.Match.OnKill(1, 6, "g19s", false); // a dead shooter's bullet still counts, as in CS
    CHECK_EQ(f.Player(1).Stats.Kills, 1);
}

TEST(Match_TeamKillCostsMoneyAndNoKillCredit)
{
    Fixture f;
    f.Match.StartMatch();
    f.GoLive();
    f.Match.OnKill(6, 7, "m4a1", false);
    CHECK_EQ(MoneyOf(f, 6), 800 - 300);
    CHECK_EQ(f.Player(6).Stats.Kills, 0);
    CHECK_EQ(f.Player(7).Stats.Deaths, 1);
}

TEST(Match_MoneyIsCappedAtMax)
{
    Fixture f;
    f.Settings.Set("mp_startmoney", 15900);
    f.Match.StartMatch();
    f.PlayRound(Side::Defenders);
    CHECK_EQ(MoneyOf(f, 7), 16000);
}

TEST(Match_DefenderTeamKillBonusWhenEnabled)
{
    Fixture f;
    f.Settings.Set("cash_team_defenders_per_kill", 50);
    f.Match.StartMatch();
    f.GoLive();
    f.Match.OnKill(6, 1, "m4a1", false);
    CHECK_EQ(MoneyOf(f, 6), 800 + 300 + 50);
    CHECK_EQ(MoneyOf(f, 7), 800 + 50);
}

// ---------------------------------------------------------------- bomb

TEST(Match_BombExplosionWinsForAttackers)
{
    Fixture f;
    f.Match.StartMatch();
    f.GoLive();
    const PlayerId planter = f.Match.GetBombCarrier();
    CHECK(f.Match.OnBombPlanted(planter, 1));
    CHECK_EQ(f.Match.GetPhase(), Phase::BombPlanted);
    CHECK_EQ(f.Match.GetPhaseTimeLeft(), 40.0);
    CHECK_EQ(f.Match.GetBombSite(), 1);
    CHECK_EQ(MoneyOf(f, planter), 800 + 300);

    // After the plant, wiping out either team does not end the round.
    f.KillAll(Side::Attackers);
    CHECK_EQ(f.Match.GetPhase(), Phase::BombPlanted);

    f.Match.Tick(40.0);
    CHECK_EQ(f.Match.GetHistory().back().Reason, RoundEndReason::BombExploded);
    CHECK_EQ(f.Match.GetHistory().back().WinnerSide, Side::Attackers);
    CHECK_EQ(f.Match.GetHistory().back().Mvp, planter);
    CHECK_EQ(MoneyOf(f, planter), 800 + 300 + 3500);
}

TEST(Match_DefuseWinsForDefendersAndPaysPlantedBonusToLosers)
{
    Fixture f;
    f.Match.StartMatch();
    f.GoLive();
    const PlayerId planter = f.Match.GetBombCarrier();
    REQUIRE(f.Match.OnBombPlanted(planter, 0));
    const PlayerId otherAttacker = planter == 1 ? 2 : 1;

    CHECK(f.Match.OnBombDefused(8));
    CHECK_EQ(f.Match.GetHistory().back().Reason, RoundEndReason::BombDefused);
    CHECK_EQ(f.Match.GetHistory().back().Mvp, static_cast<PlayerId>(8));
    CHECK_EQ(MoneyOf(f, 8), 800 + 300 + 3500);
    CHECK_EQ(MoneyOf(f, 7), 800 + 3500);
    CHECK_EQ(MoneyOf(f, otherAttacker), 800 + 1900 + 800);
    CHECK_EQ(MoneyOf(f, planter), 800 + 300 + 1900 + 800);
}

TEST(Match_OnlyLivingAttackersCanPlantDuringLiveRound)
{
    Fixture f;
    f.Match.StartMatch();
    CHECK(!f.Match.OnBombPlanted(1, 0)); // freeze time
    f.GoLive();
    CHECK(!f.Match.OnBombPlanted(6, 0)); // defender
    f.Match.OnKill(6, 1, "m4a1", false);
    CHECK(!f.Match.OnBombPlanted(1, 0)); // dead
    CHECK(!f.Match.OnBombDefused(6));    // nothing to defuse
    CHECK(f.Match.OnBombPlanted(2, 0));
    CHECK(!f.Match.OnBombPlanted(3, 1)); // already planted
    CHECK(!f.Match.OnBombDefused(3));    // attackers cannot defuse
}

TEST(Match_BombCarrierIsTrackedAndClearedOnDeath)
{
    Fixture f;
    f.Match.StartMatch();
    f.GoLive();
    const PlayerId carrier = f.Match.GetBombCarrier();
    f.Match.OnKill(6, carrier, "m4a1", false);
    CHECK_EQ(f.Match.GetBombCarrier(), InvalidPlayer);
    const PlayerId other = carrier == 1 ? 2 : 1;
    f.Match.OnBombCarrierChanged(other);
    CHECK_EQ(f.Match.GetBombCarrier(), other);
    f.Match.OnBombCarrierChanged(6); // defenders cannot carry it
    CHECK_EQ(f.Match.GetBombCarrier(), other);
}

// ---------------------------------------------------------------- halves and match end

TEST(Match_HalftimeSwapsSidesAndResetsEconomy)
{
    Fixture f;
    f.Match.StartMatch();
    for (int round = 0; round < 12; ++round)
    {
        f.Match.Tick(f.Settings.Get("mp_freezetime"));
        f.KillAll(round < 7 ? Side::Defenders : Side::Attackers); // team 0 (attacking) wins 7, loses 5
        f.Match.Tick(f.Settings.Get("mp_round_restart_delay"));
    }
    CHECK_EQ(f.Match.GetPhase(), Phase::Halftime);
    CHECK_EQ(f.Match.GetSide(0), Side::Defenders);
    CHECK_EQ(f.Match.GetScore(0), 7);
    CHECK_EQ(f.Match.GetScore(1), 5);

    f.Match.DrainEvents();
    f.Match.Tick(f.Settings.Get("mp_halftime_duration"));
    CHECK_EQ(f.Match.GetPhase(), Phase::FreezeTime);
    CHECK_EQ(f.Match.GetRoundNumber(), 13);
    for (const PlayerState& player : f.Match.GetPlayers())
    {
        CHECK_EQ(player.Money, 800);
    }
    CHECK_EQ(f.Match.GetLossCounter(0), 1);
    CHECK_EQ(f.Match.GetLossCounter(1), 1);

    bool resetInventory = false;
    for (const Event& event : f.Match.DrainEvents())
    {
        if (event.Type == EventType::RoundStarted) resetInventory = event.ResetInventory;
    }
    CHECK(resetInventory);

    // Team 0 now defends as SWAT and buys SWAT gear.
    InventorySnapshot empty;
    CHECK_EQ(f.Match.TryBuy(1, "usp", true, empty), BuyResult::Ok);
    CHECK_EQ(f.Match.TryBuy(6, "usp", true, empty), BuyResult::WrongTeam);
}

TEST(Match_ClinchEndsMatchAtThirteen)
{
    Fixture f;
    f.Match.StartMatch();
    for (int round = 0; round < 13; ++round)
    {
        f.TeamWinsRound(1);
    }
    CHECK_EQ(f.Match.GetPhase(), Phase::MatchEnd);
    CHECK_EQ(f.Match.GetWinner(), 1);
    CHECK_EQ(f.Match.GetScore(1), 13);
    CHECK_EQ(f.Match.GetRoundsPlayed(), 13);
}

TEST(Match_WithoutClinchAllRegulationRoundsArePlayed)
{
    Fixture f;
    f.Settings.Set("mp_match_can_clinch", 0);
    f.Match.StartMatch();
    for (int round = 0; round < 24; ++round)
    {
        f.TeamWinsRound(round < 20 ? 0 : 1);
        if (round < 23) CHECK(f.Match.GetPhase() != Phase::MatchEnd);
    }
    CHECK_EQ(f.Match.GetPhase(), Phase::MatchEnd);
    CHECK_EQ(f.Match.GetWinner(), 0);
    CHECK_EQ(f.Match.GetScore(0), 20);
}

TEST(Match_TiedRegulationGoesToOvertimeWithMr3Rules)
{
    Fixture f;
    f.Match.StartMatch();
    for (int round = 0; round < 24; ++round)
    {
        f.TeamWinsRound(round % 2);
    }
    // 12:12 -> overtime 1, round 25, same sides as the second half, $12,500 each.
    CHECK_EQ(f.Match.GetPhase(), Phase::FreezeTime);
    CHECK(f.Match.IsOvertime());
    CHECK_EQ(f.Match.GetOvertimeIndex(), 1);
    CHECK_EQ(f.Match.GetRoundNumber(), 25);
    CHECK_EQ(f.Match.GetSide(0), Side::Defenders);
    for (const PlayerState& player : f.Match.GetPlayers())
    {
        CHECK_EQ(player.Money, 12500);
    }

    // Three overtime rounds, then the sides swap.
    for (int round = 0; round < 3; ++round)
    {
        f.TeamWinsRound(round % 2);
    }
    CHECK_EQ(f.Match.GetSide(0), Side::Attackers);
    CHECK_EQ(MoneyOf(f, 1), 12500);

    // 14:13 now (team 0 won 2 of 3). Tie it at 15:15 to reach overtime 2.
    f.TeamWinsRound(1);
    f.TeamWinsRound(0);
    f.TeamWinsRound(1);
    CHECK_EQ(f.Match.GetScore(0), 15);
    CHECK_EQ(f.Match.GetScore(1), 15);
    CHECK_EQ(f.Match.GetOvertimeIndex(), 2);
    CHECK_EQ(f.Match.GetSide(0), Side::Attackers); // no swap at an overtime boundary

    // Overtime 2: first to 19.
    for (int round = 0; round < 4; ++round)
    {
        f.TeamWinsRound(0);
    }
    CHECK_EQ(f.Match.GetPhase(), Phase::MatchEnd);
    CHECK_EQ(f.Match.GetWinner(), 0);
    CHECK_EQ(f.Match.GetScore(0), 19);
}

TEST(Match_TiedRegulationIsDrawWithoutOvertime)
{
    Fixture f;
    f.Settings.Set("mp_overtime_enable", 0);
    f.Match.StartMatch();
    for (int round = 0; round < 24; ++round)
    {
        f.TeamWinsRound(round % 2);
    }
    CHECK_EQ(f.Match.GetPhase(), Phase::MatchEnd);
    CHECK_EQ(f.Match.GetWinner(), NoTeam);
}

TEST(Match_LargeTickPlaysThroughTimedOutRounds)
{
    Fixture f;
    f.Match.StartMatch();
    // Each untouched round lasts 15 + 115.2 + 7 = 137.2 s and goes to the defenders on time.
    f.Match.Tick(137.2 * 3 + 1.0);
    CHECK_EQ(f.Match.GetRoundsPlayed(), 3);
    CHECK_EQ(f.Match.GetScore(1), 3);
    CHECK_EQ(f.Match.GetPhase(), Phase::FreezeTime);
}

// ---------------------------------------------------------------- buying

TEST(Match_BuyingFollowsCs2Rules)
{
    Fixture f;
    f.Match.StartMatch();
    InventorySnapshot empty;

    CHECK_EQ(f.Match.TryBuy(1, "akm", false, empty), BuyResult::NotInBuyZone);
    CHECK_EQ(f.Match.TryBuy(1, "akm", true, empty), BuyResult::NotEnoughMoney);
    CHECK_EQ(f.Match.TryBuy(1, "m4a1", true, empty), BuyResult::WrongTeam);
    CHECK_EQ(f.Match.TryBuy(1, "defuse_kit", true, empty), BuyResult::WrongTeam);
    CHECK_EQ(f.Match.TryBuy(6, "defuse_kit", true, empty), BuyResult::Ok);
    CHECK_EQ(f.Match.TryBuy(1, "laser", true, empty), BuyResult::UnknownItem);
    CHECK_EQ(f.Match.TryBuy(42, "akm", true, empty), BuyResult::NotPlaying);

    f.Match.DrainEvents();
    CHECK_EQ(f.Match.TryBuy(1, "flashbang", true, empty), BuyResult::Ok);
    CHECK_EQ(MoneyOf(f, 1), 600);
    const auto events = f.Match.DrainEvents();
    REQUIRE(f.CountEvents(events, EventType::ItemPurchased) == 1);

    InventorySnapshot twoFlashes;
    twoFlashes.Counts["flashbang"] = 2;
    twoFlashes.Grenades = 2;
    CHECK_EQ(f.Match.TryBuy(1, "flashbang", true, twoFlashes), BuyResult::CarryLimit);

    InventorySnapshot fourGrenades;
    fourGrenades.Grenades = 4;
    CHECK_EQ(f.Match.TryBuy(1, "smoke", true, fourGrenades), BuyResult::GrenadeLimit);
}

TEST(Match_BuyWindowClosesTwentySecondsIntoLiveRound)
{
    Fixture f;
    f.Match.StartMatch();
    InventorySnapshot empty;
    f.GoLive();
    f.Match.Tick(19.0);
    CHECK_EQ(f.Match.TryBuy(1, "smoke", true, empty), BuyResult::Ok);
    f.Match.Tick(1.5);
    CHECK_EQ(f.Match.TryBuy(1, "flashbang", true, empty), BuyResult::BuyTimeOver);
    CHECK(!f.Match.CanBuy(1));
}

TEST(Match_DeadPlayersCannotBuy)
{
    Fixture f;
    f.Match.StartMatch();
    f.GoLive();
    f.Match.OnKill(6, 1, "m4a1", false);
    InventorySnapshot empty;
    CHECK_EQ(f.Match.TryBuy(1, "smoke", true, empty), BuyResult::Dead);
}

TEST(Match_FactionSettingDecidesWhoBuysWhat)
{
    Fixture f;
    f.Settings.Set("mp_attackers_faction", 1); // SWAT attacks
    f.Match.StartMatch();
    CHECK_EQ(f.Match.GetFaction(Side::Attackers), Faction::Swat);
    InventorySnapshot empty;
    CHECK_EQ(f.Match.TryBuy(1, "usp", true, empty), BuyResult::Ok);       // team 0 attacks as SWAT
    CHECK_EQ(f.Match.TryBuy(6, "g19s", true, empty), BuyResult::Ok);      // team 1 defends as suspects
    CHECK_EQ(f.Match.TryBuy(6, "defuse_kit", true, empty), BuyResult::Ok); // the kit follows the side
}

// ---------------------------------------------------------------- stats

TEST(Match_AssistNeedsMoreThanFortyDamage)
{
    Fixture f;
    f.Match.StartMatch();
    f.GoLive();
    f.Match.OnDamage(7, 1, 41);
    f.Match.OnKill(6, 1, "m4a1", false);
    f.Match.OnDamage(8, 2, 40);
    f.Match.OnKill(6, 2, "m4a1", false);
    CHECK_EQ(f.Player(7).Stats.Assists, 1);
    CHECK_EQ(f.Player(8).Stats.Assists, 0);
    CHECK_EQ(f.Player(6).Stats.Assists, 0);
}

TEST(Match_DamageStatsCapAtVictimHealthAndIgnoreTeammates)
{
    Fixture f;
    f.Match.StartMatch();
    f.GoLive();
    f.Match.OnDamage(6, 1, 70);
    f.Match.OnDamage(7, 1, 70); // only 30 health was left
    f.Match.OnDamage(6, 7, 50); // teammate
    CHECK_EQ(f.Player(6).Stats.Damage, 70);
    CHECK_EQ(f.Player(7).Stats.Damage, 30);
}

TEST(Match_MvpPrefersKillsThenDamage)
{
    Fixture f;
    f.Match.StartMatch();
    f.GoLive();
    f.Match.OnDamage(7, 1, 100);
    f.Match.OnKill(6, 1, "m4a1", false);
    f.Match.OnKill(7, 2, "m4a1", false);
    f.Match.OnDamage(6, 3, 10);
    f.Match.OnKill(6, 3, "m4a1", false);
    f.Match.OnKill(7, 4, "m4a1", false);
    f.Match.OnDamage(7, 5, 20);
    f.Match.OnKill(8, 5, "m4a1", false);
    // 6 and 7 both have two kills; 7 dealt more damage (100 + 20 vs 10).
    CHECK_EQ(f.Match.GetHistory().back().Mvp, static_cast<PlayerId>(7));
    CHECK_EQ(f.Player(7).Stats.Mvps, 1);
}

// ---------------------------------------------------------------- warmup, pause, roster

TEST(Match_WarmupRespawnsAndThenStartsMatch)
{
    Fixture f;
    f.Match.StartWarmup();
    CHECK_EQ(f.Match.GetPhase(), Phase::Warmup);
    CHECK_EQ(MoneyOf(f, 1), 16000);
    InventorySnapshot empty;
    CHECK_EQ(f.Match.TryBuy(1, "akm", true, empty), BuyResult::Ok);

    f.Match.DrainEvents();
    f.Match.OnKill(6, 1, "m4a1", false);
    const auto events = f.Match.DrainEvents();
    CHECK_EQ(f.CountEvents(events, EventType::Respawn), 1);
    CHECK(f.Player(1).Alive);
    CHECK_EQ(MoneyOf(f, 1), 16000);
    CHECK_EQ(f.Player(6).Stats.Kills, 0); // warmup kills do not count

    f.Match.Tick(60.0);
    CHECK_EQ(f.Match.GetPhase(), Phase::FreezeTime);
    CHECK_EQ(f.Match.GetRoundNumber(), 1);
    CHECK_EQ(MoneyOf(f, 1), 800);
}

TEST(Match_PauseTakesEffectAtNextFreezeTime)
{
    Fixture f;
    f.Match.StartMatch();
    f.GoLive();
    f.Match.RequestPause();
    CHECK(f.Match.IsPausePending());
    CHECK(!f.Match.IsPaused());
    f.KillAll(Side::Attackers);
    f.Match.Tick(7.0);
    CHECK_EQ(f.Match.GetPhase(), Phase::FreezeTime);
    CHECK(f.Match.IsPaused());

    f.Match.Tick(100.0);
    CHECK_EQ(f.Match.GetPhase(), Phase::FreezeTime);
    CHECK_EQ(f.Match.GetPhaseTimeLeft(), 15.0);

    f.Match.Unpause();
    f.Match.Tick(15.0);
    CHECK_EQ(f.Match.GetPhase(), Phase::Live);
}

TEST(Match_MidRoundJoinerWaitsForNextRound)
{
    Fixture f;
    f.Match.StartMatch();
    f.GoLive();
    CHECK(f.Match.AddPlayer(11, 0));
    CHECK(!f.Match.AddPlayer(11, 1)); // duplicate id
    CHECK(!f.Player(11).Alive);
    CHECK_EQ(MoneyOf(f, 11), 800);
    f.KillAll(Side::Attackers); // the joiner is dead already, so the round still ends
    CHECK_EQ(f.Match.GetPhase(), Phase::RoundEnd);
    f.FinishRoundEnd();
    CHECK(f.Player(11).Alive);
}

TEST(Match_LastAttackerLeavingGivesDefendersTheRound)
{
    Fixture f;
    f.Match.StartMatch();
    f.GoLive();
    for (PlayerId id = 1; id <= 4; ++id)
    {
        f.Match.OnKill(6, id, "m4a1", false);
    }
    CHECK_EQ(f.Match.GetPhase(), Phase::Live);
    CHECK(f.Match.RemovePlayer(5));
    CHECK_EQ(f.Match.GetPhase(), Phase::RoundEnd);
    CHECK_EQ(f.Match.GetHistory().back().Reason, RoundEndReason::AttackersEliminated);
}

TEST(Match_SpectatorsDoNotPlayOrBlockEliminations)
{
    Fixture f;
    CHECK(f.Match.AddPlayer(20, NoTeam));
    f.Match.StartMatch();
    CHECK(!f.Player(20).Alive);
    InventorySnapshot empty;
    CHECK_EQ(f.Match.TryBuy(20, "smoke", true, empty), BuyResult::NotPlaying);
    f.GoLive();
    f.KillAll(Side::Defenders);
    CHECK_EQ(f.Match.GetHistory().back().Reason, RoundEndReason::DefendersEliminated);
}

TEST(Match_FullMatchIsDeterministic)
{
    // Two identical scripted matches (with overtime) must produce identical histories.
    auto play = [](std::vector<RoundRecord>& history, int& winner) {
        Fixture f;
        f.Match.StartMatch();
        int round = 0;
        while (f.Match.GetPhase() != Phase::MatchEnd && round < 60)
        {
            f.GoLive();
            if (round % 5 == 0)
            {
                f.Match.OnBombPlanted(f.Match.GetBombCarrier(), round % 2);
                f.Match.Tick(40.0);
            }
            else
            {
                f.KillAll((round * 7) % 3 == 0 ? Side::Attackers : Side::Defenders);
            }
            f.FinishRoundEnd();
            ++round;
        }
        history = f.Match.GetHistory();
        winner = f.Match.GetWinner();
    };

    std::vector<RoundRecord> first, second;
    int firstWinner = NoTeam, secondWinner = NoTeam;
    play(first, firstWinner);
    play(second, secondWinner);
    REQUIRE(first.size() == second.size());
    CHECK(first.size() >= 13);
    CHECK_EQ(firstWinner, secondWinner);
    CHECK(firstWinner != NoTeam);
    for (std::size_t i = 0; i < first.size(); ++i)
    {
        CHECK_EQ(first[i].WinnerTeam, second[i].WinnerTeam);
        CHECK_EQ(first[i].Reason, second[i].Reason);
        CHECK_EQ(first[i].Mvp, second[i].Mvp);
    }
}
