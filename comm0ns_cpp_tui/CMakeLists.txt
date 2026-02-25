cmake_minimum_required(VERSION 3.16)
project(comm0ns_cpp_tui LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Curses REQUIRED)

add_executable(comm0ns_tui
    src/main.cpp
)

target_include_directories(comm0ns_tui PRIVATE ${CURSES_INCLUDE_DIR})
target_link_libraries(comm0ns_tui PRIVATE ${CURSES_LIBRARIES})
