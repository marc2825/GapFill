CXX ?= g++
CXXFLAGS ?= -std=c++20 -O2 -Wall -Wextra -Wpedantic -Wconversion
CPPFLAGS := -Isrc -Ithird_party/lodepng
PHASE5_PYTHON ?= python3

CORE_SOURCES := $(wildcard src/core/*.cpp) \
                src/cli/arguments.cpp \
                $(wildcard src/io/*.cpp) \
                $(wildcard src/predictors/*.cpp) \
                $(wildcard src/ui/*.cpp) \
                src/plugin_entry/gap_assist_command.cpp

.PHONY: all test test-e2e test-safety test-phase5 clean

all: build/gap_assist_cli build/gap_assist_tests build/gap_assist_phase2_fixtures build/gap_assist_phase4_detection_probe build/gap_assist_phase5_prediction_probe build/gap_assist_host_contract_probe

build:
	mkdir -p build

build/lodepng.o: third_party/lodepng/lodepng.cpp | build
	$(CXX) $(CPPFLAGS) -std=c++20 -O2 -w -c $< -o $@

build/gap_assist_cli: $(CORE_SOURCES) src/cli/main.cpp build/lodepng.o | build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@

build/gap_assist_tests: $(CORE_SOURCES) tests/test_main.cpp build/lodepng.o | build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@

build/gap_assist_phase2_fixtures: $(CORE_SOURCES) ../tests/parity/csp_phase2_fixture_reader.cpp build/lodepng.o | build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@

build/gap_assist_phase4_detection_probe: $(CORE_SOURCES) ../tests/parity/csp_phase4_detection_probe.cpp build/lodepng.o | build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@

build/gap_assist_phase5_prediction_probe: $(CORE_SOURCES) ../tests/parity/csp_phase5_prediction_probe.cpp build/lodepng.o | build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@

build/gap_assist_host_contract_probe: $(CORE_SOURCES) src/plugin_entry/host_contract_probe.cpp build/lodepng.o | build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@

build/gap_assist_cli_fixture: src/io/png_io.cpp tests/cli_fixture.cpp build/lodepng.o | build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@

test: build/gap_assist_tests build/gap_assist_phase2_fixtures build/gap_assist_phase4_detection_probe
	./build/gap_assist_tests
	./build/gap_assist_phase2_fixtures ../tests/fixtures/gapfill/parity/csp_detection_current.csv
	python3 ../tests/parity/test_csp_phase4_detection.py ./build/gap_assist_phase4_detection_probe
	$(MAKE) test-safety

test-safety: all build/gap_assist_cli_fixture
	python3 tests/phase3_cli_safety.py ./build/gap_assist_cli ./build/gap_assist_cli_fixture

test-phase5: build/gap_assist_phase5_prediction_probe
	$(PHASE5_PYTHON) ../tests/parity/test_csp_phase5_prediction.py ./build/gap_assist_phase5_prediction_probe ../web/public/models/unet32.onnx

test-e2e: all build/gap_assist_cli_fixture
	./build/gap_assist_cli_fixture create build/e2e/input.png
	./build/gap_assist_cli_fixture create-decisions build/e2e/decisions.txt
	./build/gap_assist_cli --input build/e2e/input.png --decisions build/e2e/decisions.txt --apply-high --force
	./build/gap_assist_cli_fixture verify build/e2e/input.gap-corrections.png

clean:
	rm -rf build
