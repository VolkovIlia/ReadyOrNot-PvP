#include "TestHelpers.h"

using namespace RonComp;

TEST(Settings_DefaultsMatchCs2Competitive)
{
    Settings settings;
    CHECK_EQ(settings.GetInt("mp_maxrounds"), 24);
    CHECK_EQ(settings.GetInt("mp_startmoney"), 800);
    CHECK_EQ(settings.GetInt("mp_maxmoney"), 16000);
    CHECK_EQ(settings.GetInt("mp_overtime_maxrounds"), 6);
    CHECK_EQ(settings.GetInt("mp_overtime_startmoney"), 12500);
    CHECK_EQ(settings.GetInt("mp_c4timer"), 40);
    CHECK_EQ(settings.GetInt("cash_team_loser_bonus"), 1400);
    CHECK_EQ(settings.GetInt("cash_team_loser_bonus_step"), 500);
    CHECK(settings.GetBool("mp_match_can_clinch"));
}

TEST(Settings_SetRejectsUnknownAndOutOfRange)
{
    Settings settings;
    std::string error;
    CHECK(!settings.Set("mp_does_not_exist", 1, &error));
    CHECK(error.find("unknown") != std::string::npos);
    CHECK(!settings.Set("mp_maxrounds", 1000, &error));
    CHECK_EQ(settings.GetInt("mp_maxrounds"), 24);
    CHECK(settings.Set("mp_maxrounds", 30));
    CHECK_EQ(settings.GetInt("mp_maxrounds"), 30);
    settings.ResetToDefaults();
    CHECK_EQ(settings.GetInt("mp_maxrounds"), 24);
}

TEST(Settings_GetUnknownThrows)
{
    Settings settings;
    bool threw = false;
    try
    {
        settings.Get("nope");
    }
    catch (const std::invalid_argument&)
    {
        threw = true;
    }
    CHECK(threw);
}

TEST(Settings_LoadFromTextAppliesGoodLinesAndReportsBadOnes)
{
    Settings settings;
    const auto errors = settings.LoadFromText(
        "// header comment\n"
        "mp_freezetime 20   // trailing comment\n"
        "\n"
        "mp_roundtime abc\n"
        "mp_unknown 5\n"
        "mp_c4timer\n"
        "mp_buytime 30 extra\n"
        "mp_startmoney 1000\r\n");
    CHECK_EQ(errors.size(), static_cast<std::size_t>(4));
    CHECK_EQ(settings.GetInt("mp_freezetime"), 20);
    CHECK_EQ(settings.GetInt("mp_startmoney"), 1000);
    CHECK_EQ(settings.Get("mp_roundtime"), 1.92);
}

TEST(Settings_ShippedConfigLoadsCleanAndMatchesDefaults)
{
    const std::string path = TestFramework::DataDir() + "/competitive.cfg";
    REQUIRE(TestHelpers::FileExists(path));
    Settings settings;
    const auto errors = settings.LoadFromText(TestHelpers::ReadFile(path));
    for (const std::string& error : errors)
    {
        TestFramework::ReportFailure(__FILE__, __LINE__, "competitive.cfg " + error);
    }
    // The cfg documents the defaults: every cvar must appear there with the same value.
    for (const auto& entry : settings.All())
    {
        if (entry.second.Value != entry.second.Default)
        {
            TestFramework::ReportFailure(__FILE__, __LINE__, "competitive.cfg changes default of " + entry.first);
        }
    }
    const std::string text = TestHelpers::ReadFile(path);
    for (const auto& entry : settings.All())
    {
        if (text.find(entry.first + " ") == std::string::npos)
        {
            TestFramework::ReportFailure(__FILE__, __LINE__, "competitive.cfg does not list " + entry.first);
        }
    }
}
