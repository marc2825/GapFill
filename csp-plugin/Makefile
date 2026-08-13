CXX ?= g++
CXXFLAGS ?= -std=c++20 -O2 -Wall -Wextra -Wpedantic -Wconversion
CPPFLAGS := -Isrc -Ithird_party/lodepng

CORE_SOURCES := $(wildcard src/core/*.cpp) \
                $(wildcard src/io/*.cpp) \
                $(wildcard src/predictors/*.cpp) \
                $(wildcard src/ui/*.cpp) \
                src/plugin_entry/gap_assist_command.cpp

.PHONY: all test test-e2e clean

all: build/gap_assist_cli build/gap_assist_tests build/gap_assist_phase2_fixtures build/gap_assist_host_contract_probe

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

build/gap_assist_host_contract_probe: $(CORE_SOURCES) src/plugin_entry/host_contract_probe.cpp build/lodepng.o | build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@

build/gap_assist_cli_fixture: src/io/png_io.cpp tests/cli_fixture.cpp build/lodepng.o | build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@

test: build/gap_assist_tests build/gap_assist_phase2_fixtures
	./build/gap_assist_tests
	./build/gap_assist_phase2_fixtures ../tests/fixtures/gapfill/parity/csp_detection_current.csv

test-e2e: all build/gap_assist_cli_fixture
	./build/gap_assist_cli_fixture create build/e2e/input.png
	./build/gap_assist_cli --input build/e2e/input.png --apply-high
	./build/gap_assist_cli_fixture verify build/e2e/input.gap-corrections.png

clean:
	rm -rf build
