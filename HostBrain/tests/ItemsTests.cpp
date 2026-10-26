#include "TestHelpers.h"

#include <set>

using namespace RonComp;

TEST(Items_ParsesQuotedFieldsAndHeaderOrder)
{
    ItemCatalog catalog;
    const auto errors = catalog.LoadFromCsv(
        "game_item,id,price,name,category,faction,kill_reward,max_carry,notes\n"
        "/Game/a,a,100,\"Name, with comma\",pistol,any,300,1,\"say \"\"hi\"\"\"\n");
    CHECK(errors.empty());
    const Item* item = catalog.Find("a");
    REQUIRE(item != nullptr);
    CHECK_EQ(item->Name, std::string("Name, with comma"));
    CHECK_EQ(item->Price, 100);
    CHECK_EQ(item->GameItem, std::string("/Game/a"));
    CHECK(catalog.FindByGameItem("/Game/a") == item);
}

TEST(Items_ReportsBadRowsAndKeepsGoodOnes)
{
    ItemCatalog catalog;
    const auto errors = catalog.LoadFromCsv(
        "id,name,category,faction,price,kill_reward,max_carry,game_item\n"
        "ok,Ok,rifle,swat,100,300,1,/Game/ok\n"
        "badcat,X,laser,swat,100,300,1,/Game/x\n"
        "badfaction,X,rifle,aliens,100,300,1,/Game/x\n"
        "badprice,X,rifle,swat,-5,300,1,/Game/x\n"
        "ok,Dup,rifle,swat,100,300,1,/Game/dup\n"
        "short,X,rifle\n");
    CHECK_EQ(errors.size(), static_cast<std::size_t>(5));
    CHECK_EQ(catalog.All().size(), static_cast<std::size_t>(1));
}

TEST(Items_MissingColumnIsReported)
{
    ItemCatalog catalog;
    const auto errors = catalog.LoadFromCsv("id,name,category\nx,X,rifle\n");
    CHECK(!errors.empty());
    CHECK(catalog.All().empty());
}

TEST(Items_ShippedCatalogLoadsClean)
{
    const std::string path = TestFramework::DataDir() + "/items.csv";
    REQUIRE(TestHelpers::FileExists(path));
    ItemCatalog catalog;
    const auto errors = catalog.LoadFromCsv(TestHelpers::ReadFile(path));
    for (const std::string& error : errors)
    {
        TestFramework::ReportFailure(__FILE__, __LINE__, "items.csv " + error);
    }
    CHECK(catalog.All().size() >= 40);

    std::set<std::string> gameItems;
    for (const Item& item : catalog.All())
    {
        CHECK(item.GameItem.rfind("/Game/", 0) == 0);
        CHECK(gameItems.insert(item.GameItem).second);
    }

    const Item* kit = catalog.Find("defuse_kit");
    REQUIRE(kit != nullptr);
    CHECK(kit->Access == ItemAccess::Defenders);
    CHECK_EQ(kit->Category, ItemCategory::Kit);

    // Both factions need a free-ish default pistol and something to buy in every weapon tier.
    for (const char* id : {"usp", "g19s", "m4a1", "akm", "m24", "flashbang", "smoke", "armor_light"})
    {
        CHECK(catalog.Find(id) != nullptr);
    }
}
