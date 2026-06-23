#include "core/settings.hpp"

#include <algorithm>
#include <fstream>
#include <stdexcept>
#include <string>
#include <unordered_map>

namespace gap_assist {
namespace {

bool parseBool(const std::string& value) {
  return value == "1" || value == "true" || value == "yes";
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
  if (!stream) return settings;
  std::unordered_map<std::string, std::string> values;
  for (std::string line; std::getline(stream, line);) {
    if (line.empty() || line[0] == '#') continue;
    const auto separator = line.find('=');
    if (separator == std::string::npos) continue;
    values[line.substr(0, separator)] = line.substr(separator + 1);
  }
  try {
    if (const auto it = values.find("mode"); it != values.end()) {
      settings.mode = it->second == "quick_fix"   ? RunMode::QuickFix
                      : it->second == "one_by_one" ? RunMode::OneByOne
                                                     : RunMode::ReviewList;
    }
    if (const auto it = values.find("gap_size"); it != values.end()) {
      settings.gapSizePreset = it->second == "small"   ? GapSizePreset::Small
                               : it->second == "large" ? GapSizePreset::Large
                               : it->second == "custom" ? GapSizePreset::Custom
                                                         : GapSizePreset::Medium;
    }
    if (const auto it = values.find("custom_gap_threshold"); it != values.end())
      settings.customGapThreshold = std::stoull(it->second);
    if (const auto it = values.find("gap_threshold"); it != values.end()) {
      settings.customGapThreshold = std::stoull(it->second);
      if (values.find("gap_size") == values.end())
        settings.gapSizePreset = GapSizePreset::Custom;
    }
    settings.gapThreshold =
        presetThreshold(settings.gapSizePreset, settings.customGapThreshold);
    if (settings.gapThreshold == 0)
      throw std::invalid_argument("Gap threshold must be greater than zero.");
    if (const auto it = values.find("alpha_threshold"); it != values.end())
      settings.alphaThreshold = static_cast<std::uint8_t>(
          std::clamp(std::stoi(it->second), 0, 255));
    if (const auto it = values.find("confidence"); it != values.end()) {
      settings.confidencePreset =
          it->second == "conservative"   ? ConfidencePreset::Conservative
          : it->second == "aggressive"   ? ConfidencePreset::Aggressive
                                           : ConfidencePreset::Balanced;
    }
    if (const auto it = values.find("output"); it != values.end())
      settings.outputMode = it->second == "overwrite" ? OutputMode::OverwriteActiveLayer
                                                       : OutputMode::CorrectionLayer;
    if (const auto it = values.find("scope"); it != values.end())
      settings.scope = it->second == "selection" ? Scope::SelectionOnly : Scope::WholeLayer;
    if (const auto it = values.find("connectivity"); it != values.end())
      settings.connectivity = it->second == "8" ? Connectivity::Eight : Connectivity::Four;
    if (const auto it = values.find("sampling_radius"); it != values.end())
      settings.samplingRadius = std::max(1, std::stoi(it->second));
    if (const auto it = values.find("owner_color_tolerance"); it != values.end())
      settings.ownerColorTolerance = std::clamp(std::stoi(it->second), 0, 765);
    if (const auto it = values.find("create_highlight"); it != values.end())
      settings.createHighlightLayer = parseBool(it->second);
    if (const auto it = values.find("predictor"); it != values.end())
      settings.predictorOnnx = it->second == "onnx";
  } catch (const std::exception&) {
    throw std::runtime_error("Gap Assist settings file contains an invalid value: " +
                             path.string());
  }
  return settings;
}

void SettingsStore::save(const std::filesystem::path& path, const Settings& settings) {
  if (path.has_parent_path()) std::filesystem::create_directories(path.parent_path());
  std::ofstream stream(path, std::ios::trunc);
  if (!stream) throw std::runtime_error("Cannot write settings: " + path.string());
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
}

}  // namespace gap_assist
