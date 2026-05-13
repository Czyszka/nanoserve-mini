cmake_minimum_required(VERSION 3.16)
project(token_buffer_public_tests CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT DEFINED WORK_DIR)
  message(FATAL_ERROR "WORK_DIR must be set (path to the agent's work dir containing starter/).")
endif()

add_subdirectory("${WORK_DIR}/starter" starter_build)

add_executable(test_token_buffer_public test_token_buffer_public.cpp)
target_link_libraries(test_token_buffer_public PRIVATE token_buffer)
