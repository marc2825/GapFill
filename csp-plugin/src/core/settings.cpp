#include "core/settings.hpp"

#include <algorithm>
#include <charconv>
#include <fstream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>

namespace gap_assist {
namespace {

bool parseBool(const std::string& value) {
  if (value == "1" || value == "true" || value == "yes") return true;
  if (value == "0" || value == "false" || value == "no") return false;
  throw std::invalid_argument("Boolean setting must be true or false.");
}

std::size_t parseSize(const std::string& value) {
  std::size_t parsed = 0;
  const auto [end, error] =
      std::from_chars(value.data(), value.data() + value.size(), parsed);
  if (value.empty() || error != std::errc{} || end != value.data() + value.size())
    throw std::invalid_argument("Setting must be an unsigned integer.");
  return parsed;
}

int parseInt(const std::string& value) {
  int parsed = 0;
  const auto [end, error] =
      std::from_chars(value.data(), value.data() + value.size(), parsed);
  if (value.empty() || error != std::errc{} || end != value.data() + value.size())
    throw std::invalid_argument("Setting must be an integer.");
  return parsed;
}

std::string modeName(RunMode mode) {
  if (mode == RunMode::QuickFix) return "quick_fix";
  if (mode == RunMode::OneByOne) return "one_by_one";
  return "review_list";
}

std::string confidenceName(ConfidencePreset preset) {
  if (preset == ConfidencePreset::Conservative) return "conservative";
  if (preset == ConfidencePreset::Aggressive) return "aggressive";
  return "balanced";
}

std::string gapSizeName(GapSizePreset preset) {
  if (preset == GapSizePreset::Small) return "small";
  if (preset == GapSizePreset::Large) return "large";
  if (preset == GapSizePreset::Custom) return "custom";
  return "medium";
}

std::size_t presetThreshold(GapSizePreset preset, std::size_t custom) {
  if (preset == GapSizePreset::Small) return 3;
  if (preset == GapSizePreset::Large) return 30;
  if (preset == GapSizePreset::Custom) return custom;
  return 10;
}

}  // namespace

ConfidenceThresholds thresholdsFor(ConfidencePreset preset) {
  switch (preset) {
    case ConfidencePreset::Conservative:
      return {0.90, 0.65};
    case ConfidencePreset::Balanced:
      return {0.85, 0.55};
    case ConfidencePreset::Aggressive:
      return {0.75, 0.45};
  }
  return {0.85, 0.55};
}

ConfidenceBand classifyConfidence(double confidence, ConfidencePreset preset) {
  const auto thresholds = thresholdsFor(preset);
  if (confidence >= thresholds.high) return ConfidenceBand::High;
  if (confidence >= thresholds.medium) return ConfidenceBand::Medium;
  return ConfidenceBand::Low;
}

Settings SettingsStore::load(const std::filesystem::path& path) {
  Settings settings;
  std::ifstream stream(path);
  if (!stream) throw std::runtime_error("Cannot read settings: " + path.string());
  std::unordered_map<std::string, std::string> values;
  for (std::string line; std::getline(stream, line);) {
    if (line.empty() || line[0] == '#') continue;
    const auto separator = line.find('=');
    if (separator == std::string::npos || separator == 0)
      throw std::runtime_error("Gap Assist settings file contains an invalid line: " +
                               path.string());
    const auto key = line.substr(0, separator);
    const auto value = line.substr(separator + 1);
    if (key != "mode" && key != "gap_size" && key != "custom_gap_threshold" &&
        key != "gap_threshold" && key != "alpha_threshold" &&
        key != "confidence" && key != "output" && key != "scope" &&
        key != "connectivity" && key != "sampling_radius" &&
        key != "owner_color_tolerance" && key != "create_highlight" &&
        key != "predictor") {
      throw std::runtime_error("Gap Assist settings file contains an unknown key: " +
                               key);
    }
    values[key] = value;
  }
  try {
    if (const auto it = values.find("mode"); it != values.end()) {
      if (it->second == "quick_fix")
        settings.mode = RunMode::QuickFix;
      else if (it->second == "one_by_one")
        settings.mode = RunMode::OneByOne;
      else if (it->second == "review_list")
        settings.mode = RunMode::ReviewList;
      else
        throw std::invalid_argument("Invalid mode.");
    }
    if (const auto it = values.find("gap_size"); it != values.end()) {
      if (it->second == "small")
        settings.gapSizePreset = GapSizePreset::Small;
      else if (it->second == "medium")
        settings.gapSizePreset = GapSizePreset::Medium;
      else if (it->second == "large")
        settings.gapSizePreset = GapSizePreset::Large;
      else if (it->second == "custom")
        settings.gapSizePreset = GapSizePreset::Custom;
      else
        throw std::invalid_argument("Invalid gap_size.");
    }
    if (const auto it = values.find("custom_gap_threshold"); it != values.end()) {
      settings.customGapThreshold = parseSize(it->second);
      if (settings.customGapThreshold == 0)
        throw std::invalid_argument("Custom gap threshold must be positive.");
    }
    if (const auto it = values.find("gap_threshold"); it != values.end()) {
      settings.customGapThreshold = parseSize(it->second);
      if (settings.customGapThreshold == 0)
        throw std::invalid_argument("Gap threshold must be positive.");
      if (values.find("gap_size") == values.end())
        settings.gapSizePreset = GapSizePreset::Custom;
    }
    settings.gapThreshold =
        presetThreshold(settings.gapSizePreset, settings.customGapThreshold);
    if (settings.gapThreshold == 0)
      throw std::invalid_argument("Gap threshold must be greater than zero.");
    if (const auto it = values.find("alpha_threshold"); it != values.end()) {
      const int value = parseInt(it->second);
      if (value < 0 || value > 255)
        throw std::invalid_argument("Alpha threshold must be 0..255.");
      settings.alphaThreshold = static_cast<std::uint8_t>(value);
    }
    if (const auto it = values.find("confidence"); it != values.end()) {
      if (it->second == "conservative")
        settings.confidencePreset = ConfidencePreset::Conservative;
      else if (it->second == "balanced")
        settings.confidencePreset = ConfidencePreset::Balanced;
      else if (it->second == "aggressive")
        settings.confidencePreset = ConfidencePreset::Aggressive;
      else
        throw std::invalid_argument("Invalid confidence preset.");
    }
    if (const auto it = values.find("output"); it != values.end()) {
      if (it->second == "overwrite")
        settings.outputMode = OutputMode::OverwriteActiveLayer;
      else if (it->second == "correction_layer")
        settings.outputMode = OutputMode::CorrectionLayer;
      else
        throw std::invalid_argument("Invalid output mode.");
    }
    if (const auto it = values.find("scope"); it != values.end()) {
      if (it->second == "selection")
        settings.scope = Scope::SelectionOnly;
      else if (it->second == "whole")
        settings.scope = Scope::WholeLayer;
      else
        throw std::invalid_argument("Invalid scope.");
    }
    if (const auto it = values.find("connectivity"); it != values.end()) {
      if (it->second == "8")
        settings.connectivity = Connectivity::Eight;
      else if (it->second == "4")
        settings.connectivity = Connectivity::Four;
      else
        throw std::invalid_argument("Invalid connectivity.");
    }
    if (const auto it = values.find("sampling_radius"); it != values.end()) {
      settings.samplingRadius = parseInt(it->second);
      if (settings.samplingRadius < 1)
        throw std::invalid_argument("Sampling radius must be positive.");
    }
    if (const auto it = values.find("owner_color_tolerance"); it != values.end()) {
      settings.ownerColorTolerance = parseInt(it->second);
      if (settings.ownerColorTolerance < 0 || settings.ownerColorTolerance > 765)
        throw std::invalid_argument("Owner color tolerance must be 0..765.");
    }
    if (const auto it = values.find("create_highlight"); it != values.end())
      settings.createHighlightLayer = parseBool(it->second);
    if (const auto it = values.find("predictor"); it != values.end()) {
      if (it->second == "onnx")
        settings.predictorOnnx = true;
      else if (it->second == "rule_based")
        settings.predictorOnnx = false;
      else
        throw std::invalid_argument("Invalid predictor.");
    }
  } catch (const std::exception&) {
    throw std::runtime_error("Gap Assist settings file contains an invalid value: " +
                             path.string());
  }
  return settings;
}

std::string serializeSettings(const Settings& settings) {
  std::ostringstream stream;
  stream << "# Gap Assist settings (no image data or telemetry)\n";
  stream << "mode=" << modeName(settings.mode) << '\n';
  stream << "gap_size=" << gapSizeName(settings.gapSizePreset) << '\n';
  stream << "custom_gap_threshold=" << settings.customGapThreshold << '\n';
  stream << "alpha_threshold=" << static_cast<int>(settings.alphaThreshold) << '\n';
  stream << "confidence=" << confidenceName(settings.confidencePreset) << '\n';
  stream << "output="
         << (settings.outputMode == OutputMode::OverwriteActiveLayer ? "overwrite"
                                                                      : "correction_layer")
         << '\n';
  stream << "scope=" << (settings.scope == Scope::SelectionOnly ? "selection" : "whole")
         << '\n';
  stream << "connectivity="
         << (settings.connectivity == Connectivity::Eight ? "8" : "4") << '\n';
  stream << "sampling_radius=" << settings.samplingRadius << '\n';
  stream << "owner_color_tolerance=" << settings.ownerColorTolerance << '\n';
  stream << "create_highlight=" << (settings.createHighlightLayer ? "true" : "false")
         << '\n';
  stream << "predictor=" << (settings.predictorOnnx ? "onnx" : "rule_based") << '\n';
  return stream.str();
}

void SettingsStore::save(const std::filesystem::path& path, const Settings& settings) {
  if (path.has_parent_path()) std::filesystem::create_directories(path.parent_path());
  std::ofstream stream(path, std::ios::trunc);
  if (!stream) throw std::runtime_error("Cannot write settings: " + path.string());
  stream << serializeSettings(settings);
  if (!stream) throw std::runtime_error("Cannot write settings: " + path.string());
}

}  // namespace gap_assist
