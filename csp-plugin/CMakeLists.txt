cmake_minimum_required(VERSION 3.20)
project(gap_assist_csp VERSION 0.1.0 LANGUAGES CXX)

option(GAP_ASSIST_BUILD_TESTS "Build the SDK-independent test suite" ON)
option(GAP_ASSIST_BUILD_TOOLS "Build the CLI and host-contract probe" ON)
option(GAP_ASSIST_STATIC_MSVC_RUNTIME
       "Link Gap Assist MSVC targets against the static runtime" OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

add_library(lodepng STATIC
  third_party/lodepng/lodepng.cpp
)
target_include_directories(lodepng PUBLIC third_party/lodepng)
set_target_properties(lodepng PROPERTIES CXX_EXTENSIONS OFF)

set(GAP_ASSIST_CORE_SOURCES
  src/cli/arguments.cpp
  src/core/candidate_context.cpp
  src/core/correction_output.cpp
  src/core/gap_detection.cpp
  src/core/owner_regions.cpp
  src/core/quick_fix_pipeline.cpp
  src/core/settings.cpp
  src/core/smart_gap_propagation.cpp
  src/io/png_io.cpp
  src/io/atomic_output.cpp
  src/io/review_artifacts.cpp
  src/plugin_entry/gap_assist_command.cpp
  src/plugin_entry/native_host_contract.cpp
  src/predictors/gap_color_predictor.cpp
  src/predictors/onnx_predictor_stub.cpp
  src/predictors/rule_based_predictor.cpp
  src/ui/dialog_model.cpp
  src/ui/review_session.cpp
)

add_library(gap_assist_core STATIC ${GAP_ASSIST_CORE_SOURCES})
target_compile_features(gap_assist_core PUBLIC cxx_std_20)
target_include_directories(gap_assist_core PUBLIC src)
target_link_libraries(gap_assist_core PUBLIC lodepng)

if(MSVC AND GAP_ASSIST_STATIC_MSVC_RUNTIME)
  set_property(TARGET lodepng gap_assist_core PROPERTY
               MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()

if(MSVC)
  target_compile_options(gap_assist_core PRIVATE /W4 /permissive-)
else()
  target_compile_options(gap_assist_core PRIVATE -Wall -Wextra -Wpedantic -Wconversion)
endif()

if(GAP_ASSIST_BUILD_TOOLS)
  add_executable(gap_assist_cli src/cli/main.cpp)
  target_link_libraries(gap_assist_cli PRIVATE gap_assist_core)

  add_executable(gap_assist_host_contract_probe
    src/plugin_entry/host_contract_probe.cpp
  )
  target_link_libraries(gap_assist_host_contract_probe PRIVATE gap_assist_core)
endif()

if(GAP_ASSIST_BUILD_TESTS)
  if(NOT GAP_ASSIST_BUILD_TOOLS)
    message(FATAL_ERROR "GAP_ASSIST_BUILD_TESTS requires GAP_ASSIST_BUILD_TOOLS")
  endif()
  enable_testing()
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  add_executable(gap_assist_tests tests/test_main.cpp)
  target_link_libraries(gap_assist_tests PRIVATE gap_assist_core)
  add_test(NAME gap_assist_core COMMAND gap_assist_tests)

  add_executable(gap_assist_native_host_contract_tests
                 tests/native_host_contract_test.cpp)
  target_link_libraries(gap_assist_native_host_contract_tests
                        PRIVATE gap_assist_core)
  add_test(NAME gap_assist_native_host_contract
           COMMAND gap_assist_native_host_contract_tests)

  add_executable(gap_assist_phase2_fixtures
                 ../tests/parity/csp_phase2_fixture_reader.cpp)
  target_link_libraries(gap_assist_phase2_fixtures PRIVATE gap_assist_core)
  add_test(NAME gap_assist_phase2_fixtures
           COMMAND gap_assist_phase2_fixtures
                   "${CMAKE_CURRENT_SOURCE_DIR}/../tests/fixtures/gapfill/parity/csp_detection_current.csv")

  add_executable(gap_assist_phase4_detection_probe
                 ../tests/parity/csp_phase4_detection_probe.cpp)
  target_link_libraries(gap_assist_phase4_detection_probe PRIVATE gap_assist_core)
  add_test(NAME gap_assist_phase4_detection
           COMMAND "${Python3_EXECUTABLE}"
                   "${CMAKE_CURRENT_SOURCE_DIR}/../tests/parity/test_csp_phase4_detection.py"
                   "$<TARGET_FILE:gap_assist_phase4_detection_probe>")

  add_executable(gap_assist_phase5_prediction_probe
                 ../tests/parity/csp_phase5_prediction_probe.cpp)
  target_link_libraries(gap_assist_phase5_prediction_probe PRIVATE gap_assist_core)
  execute_process(
    COMMAND "${Python3_EXECUTABLE}" -c "import numpy, onnxruntime"
    RESULT_VARIABLE GAP_ASSIST_PHASE5_PYTHON_STATUS
    OUTPUT_QUIET ERROR_QUIET)
  if(GAP_ASSIST_PHASE5_PYTHON_STATUS EQUAL 0)
    add_test(NAME gap_assist_phase5_prediction
             COMMAND "${Python3_EXECUTABLE}"
                     "${CMAKE_CURRENT_SOURCE_DIR}/../tests/parity/test_csp_phase5_prediction.py"
                     "$<TARGET_FILE:gap_assist_phase5_prediction_probe>"
                     "${CMAKE_CURRENT_SOURCE_DIR}/../web/public/models/unet32.onnx")
  else()
    message(STATUS
      "NumPy/ONNX Runtime unavailable: CSP Phase 5 cross-runtime parity is not registered")
  endif()

  add_executable(gap_assist_cli_fixture tests/cli_fixture.cpp)
  target_link_libraries(gap_assist_cli_fixture PRIVATE gap_assist_core)
  set(GAP_ASSIST_FIXTURE_DIR "${CMAKE_CURRENT_BINARY_DIR}/e2e")
  add_test(NAME gap_assist_fixture_create
           COMMAND gap_assist_cli_fixture create "${GAP_ASSIST_FIXTURE_DIR}/input.png")
  set_tests_properties(gap_assist_fixture_create PROPERTIES FIXTURES_SETUP png_fixture)
  add_test(NAME gap_assist_fixture_decisions
           COMMAND gap_assist_cli_fixture create-decisions
                   "${GAP_ASSIST_FIXTURE_DIR}/decisions.txt")
  set_tests_properties(gap_assist_fixture_decisions PROPERTIES
                       FIXTURES_SETUP png_fixture)
  add_test(NAME gap_assist_cli_smoke
           COMMAND gap_assist_cli --input "${GAP_ASSIST_FIXTURE_DIR}/input.png"
                                  --decisions "${GAP_ASSIST_FIXTURE_DIR}/decisions.txt"
                                  --apply-high --force)
  set_tests_properties(gap_assist_cli_smoke PROPERTIES FIXTURES_REQUIRED png_fixture
                       FIXTURES_SETUP cli_output)
  add_test(NAME gap_assist_fixture_verify
           COMMAND gap_assist_cli_fixture verify
                   "${GAP_ASSIST_FIXTURE_DIR}/input.gap-corrections.png")
  set_tests_properties(gap_assist_fixture_verify PROPERTIES FIXTURES_REQUIRED cli_output)

  add_test(NAME gap_assist_phase3_cli_safety
           COMMAND "${Python3_EXECUTABLE}"
                   "${CMAKE_CURRENT_SOURCE_DIR}/tests/phase3_cli_safety.py"
                   "$<TARGET_FILE:gap_assist_cli>"
                   "$<TARGET_FILE:gap_assist_cli_fixture>")
endif()

if(GAP_ASSIST_BUILD_TOOLS)
  install(TARGETS gap_assist_cli RUNTIME DESTINATION bin)
endif()
install(FILES README.md THIRD_PARTY_NOTICES.md
              docs/CSP_GAP_ASSIST_SPEC.md docs/ARCHITECTURE.md
              docs/SDK_INTEGRATION.md docs/CSP_SDK_20210827_CAPABILITIES.md
              docs/LIMITATIONS.md docs/PRIVACY.md
              docs/MANUAL_TEST_PLAN.md docs/RELEASE_CHECKLIST.md
        DESTINATION share/doc/gap-assist-csp)
install(FILES third_party/lodepng/LICENSE
        DESTINATION share/doc/gap-assist-csp/licenses
        RENAME LodePNG-LICENSE)
