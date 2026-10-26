cmake_minimum_required(VERSION 3.22)
project(HostBrain LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# Static CRT: the native guard DLL is loaded into the game process and must not depend on
# whichever VC++ runtime happens to be installed.
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

if(MSVC)
    add_compile_options(/W4 /WX /permissive- /utf-8)
else()
    add_compile_options(-Wall -Wextra -Werror -pedantic)
endif()

# Rules core: pure C++, no Unreal or UE4SS dependencies.
add_library(roncomp_core STATIC
    src/core/Types.cpp
    src/core/Settings.cpp
    src/core/Items.cpp
    src/core/Match.cpp)
target_include_directories(roncomp_core PUBLIC src)

add_executable(core_tests
    tests/TestMain.cpp
    tests/SettingsTests.cpp
    tests/ItemsTests.cpp
    tests/MatchTests.cpp)
target_link_libraries(core_tests PRIVATE roncomp_core)

enable_testing()
add_test(NAME core_tests COMMAND core_tests ${CMAKE_CURRENT_SOURCE_DIR}/../data)

# Host-only native guards loaded by the HostBrain Lua mod.
if(WIN32)
    add_library(RonCompNative SHARED native/RonCompNative.cpp)
endif()
