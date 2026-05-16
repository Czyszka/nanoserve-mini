cmake_minimum_required(VERSION 3.16)
project(token_buffer_hidden_tests CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT DEFINED WORK_DIR)
  message(FATAL_ERROR "WORK_DIR must be set.")
endif()

set(STARTER_DIR "${WORK_DIR}")
if(EXISTS "${WORK_DIR}/starter/CMakeLists.txt")
  set(STARTER_DIR "${WORK_DIR}/starter")
endif()
if(NOT EXISTS "${STARTER_DIR}/CMakeLists.txt")
  message(FATAL_ERROR "Could not find starter CMakeLists.txt under ${WORK_DIR}.")
endif()

add_subdirectory("${STARTER_DIR}" starter_build)

add_executable(test_token_buffer_hidden test_token_buffer_hidden.cpp)
target_link_libraries(test_token_buffer_hidden PRIVATE token_buffer)
