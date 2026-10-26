#include "TestFramework.h"

#include <cstring>

// Usage: core_tests [data-dir] [name-filter]
int main(int argc, char** argv)
{
    if (argc > 1)
    {
        TestFramework::DataDir() = argv[1];
    }
    const char* filter = argc > 2 ? argv[2] : nullptr;

    int run = 0;
    int failedTests = 0;
    for (const TestFramework::TestCase& test : TestFramework::Registry())
    {
        if (filter && !std::strstr(test.Name, filter))
        {
            continue;
        }
        ++run;
        const int before = TestFramework::FailureCount();
        try
        {
            test.Body();
        }
        catch (const TestFramework::RequireFailed&)
        {
        }
        catch (const std::exception& error)
        {
            TestFramework::ReportFailure(__FILE__, __LINE__, std::string("unexpected exception: ") + error.what());
        }
        const bool passed = TestFramework::FailureCount() == before;
        if (!passed)
        {
            ++failedTests;
        }
        std::cout << (passed ? "[ OK ] " : "[FAIL] ") << test.Name << "\n";
    }

    std::cout << "\n" << run - failedTests << "/" << run << " tests passed, "
              << TestFramework::FailureCount() << " failed checks\n";
    return failedTests == 0 ? 0 : 1;
}
