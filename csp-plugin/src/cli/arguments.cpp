#include "cli/arguments.hpp"

#include <charconv>
#include <cstdint>
#include <limits>
#include <optional>
#include <ostream>
#include <stdexcept>
#include <string_view>

namespace gap_assist {
namespace {

struct GapSizeOverride {
  GapSizePreset preset{GapSizePreset::Medium};
  std::size_t threshold{10};
};

struct Overrides {
  std::optional<RunMode> mode;
  std::optional<GapSizeOverride> gapSize;
  std::optional<std::uint8_t> alphaThreshold;
  std::optional<ConfidencePreset> confidence;
  std::optional<Connectivity> connectivity;
  std::optional<bool> predictorOnnx;
  std::optional<bool> createHighlightLayer;
  std::optional<bool> debugLogging;
  std::optional<Scope> scope;
};

std::string requireValue(std::size_t& index, std::span<const std::string> values) {
  if (++index >= values.size())
    throw std::invalid_argument("Missing value after " + values[index - 1]);
  return values[index];
}

std::uint64_t parseUnsigned(std::string_view value, std::string_view label) {
  if (value.empty()) throw std::invalid_argument(std::string(label) + " is required.");
  std::uint64_t parsed = 0;
  const auto [end, error] =
      std::from_chars(value.data(), value.data() + value.size(), parsed);
  if (error != std::errc{} || end != value.data() + value.size())
    throw std::invalid_argument(std::string(label) + " must be an unsigned integer.");
  return parsed;
}

GapSizeOverride parseGapSize(std::string_view value) {
  if (value == "small") return {GapSizePreset::Small, 3};
  if (value == "medium") return {GapSizePreset::Medium, 10};
  if (value == "large") return {GapSizePreset::Large, 30};
  const auto threshold = parseUnsigned(value, "Custom gap size");
  if (threshold == 0) throw std::invalid_argument("Custom gap size must be greater than zero.");
  if (threshold > std::numeric_limits<std::size_t>::max())
    throw std::invalid_argument("Custom gap size exceeds the supported range.");
  return {GapSizePreset::Custom, static_cast<std::size_t>(threshold)};
}

void applyOverrides(Settings& settings, const Overrides& overrides) {
  if (overrides.mode) settings.mode = *overrides.mode;
  if (overrides.gapSize) {
    settings.gapSizePreset = overrides.gapSize->preset;
    settings.gapThreshold = overrides.gapSize->threshold;
    if (overrides.gapSize->preset == GapSizePreset::Custom)
      settings.customGapThreshold = overrides.gapSize->threshold;
  }
  if (overrides.alphaThreshold) settings.alphaThreshold = *overrides.alphaThreshold;
  if (overrides.confidence) settings.confidencePreset = *overrides.confidence;
  if (overrides.connectivity) settings.connectivity = *overrides.connectivity;
  if (overrides.predictorOnnx) settings.predictorOnnx = *overrides.predictorOnnx;
  if (overrides.createHighlightLayer)
    settings.createHighlightLayer = *overrides.createHighlightLayer;
  if (overrides.debugLogging) settings.debugLogging = *overrides.debugLogging;
  if (overrides.scope) settings.scope = *overrides.scope;
}

}  // namespace

void printCliUsage(std::ostream& output) {
  output
      << "Gap Assist PNG harness\n\n"
      << "Usage: gap_assist_cli --input layer.png [options]\n\n"
      << "Outputs:\n"
      << "  --correction FILE     Transparent correction-layer PNG\n"
      << "  --highlight FILE      Confidence marker-layer PNG\n"
      << "  --corrected FILE      Corrected composite preview PNG\n"
      << "  --manifest FILE       JSON review manifest\n"
      << "  --contact-sheet FILE  Before/after review sheet PNG\n"
      << "  --force               Replace existing outputs; never permits aliases\n\n"
      << "Analysis:\n"
      << "  --mode quick|review|one\n"
      << "  --gap-size small|medium|large|NUMBER\n"
      << "  --alpha-threshold 0..255 (legacy owner/prediction cutoff; detection is alpha 0)\n"
      << "  --confidence conservative|balanced|aggressive\n"
      << "  --connectivity 4|8\n"
      << "  --selection FILE      Restrict application after full-image enclosure analysis\n"
      << "  --decisions FILE      Lines such as 3=apply, 4=skip, 5=mark_only\n"
      << "  --apply-high          Apply remaining unreviewed high-confidence learned gaps\n"
      << "  --predictor rule_based|onnx (ONNX requires a runtime-enabled build)\n"
      << "  --no-highlight        Do not write a highlight layer\n"
      << "  --settings FILE       Load persisted settings before CLI overrides\n"
      << "  --save-settings FILE  Save effective settings\n"
      << "  --debug               Include predictor diagnostics in the manifest\n\n"
      << "Configuration precedence is defaults < settings file < explicit CLI.\n"
      << "A repeated option uses its last occurrence.\n";
}

CliArguments parseCliArguments(std::span<const std::string> values) {
  CliArguments arguments;
  Overrides overrides;
  for (std::size_t index = 0; index < values.size(); ++index) {
    const auto& option = values[index];
    if (option == "--help" || option == "-h") {
      arguments.showHelp = true;
    } else if (option == "--settings") {
      arguments.settingsPath = requireValue(index, values);
    } else if (option == "--input") {
      arguments.input = requireValue(index, values);
    } else if (option == "--correction") {
      arguments.correction = requireValue(index, values);
    } else if (option == "--highlight") {
      arguments.highlight = requireValue(index, values);
    } else if (option == "--corrected") {
      arguments.corrected = requireValue(index, values);
    } else if (option == "--manifest") {
      arguments.manifest = requireValue(index, values);
    } else if (option == "--contact-sheet") {
      arguments.contactSheet = requireValue(index, values);
    } else if (option == "--selection") {
      arguments.selection = requireValue(index, values);
      overrides.scope = Scope::SelectionOnly;
    } else if (option == "--decisions") {
      arguments.decisions = requireValue(index, values);
    } else if (option == "--save-settings") {
      arguments.saveSettingsPath = requireValue(index, values);
    } else if (option == "--mode") {
      const auto value = requireValue(index, values);
      if (value == "quick")
        overrides.mode = RunMode::QuickFix;
      else if (value == "review")
        overrides.mode = RunMode::ReviewList;
      else if (value == "one")
        overrides.mode = RunMode::OneByOne;
      else
        throw std::invalid_argument("Invalid mode: " + value);
    } else if (option == "--gap-size") {
      overrides.gapSize = parseGapSize(requireValue(index, values));
    } else if (option == "--alpha-threshold") {
      const auto value = parseUnsigned(requireValue(index, values), "Alpha threshold");
      if (value > 255) throw std::invalid_argument("Alpha threshold must be 0..255.");
      overrides.alphaThreshold = static_cast<std::uint8_t>(value);
    } else if (option == "--confidence") {
      const auto value = requireValue(index, values);
      if (value == "conservative")
        overrides.confidence = ConfidencePreset::Conservative;
      else if (value == "balanced")
        overrides.confidence = ConfidencePreset::Balanced;
      else if (value == "aggressive")
        overrides.confidence = ConfidencePreset::Aggressive;
      else
        throw std::invalid_argument("Invalid confidence preset: " + value);
    } else if (option == "--connectivity") {
      const auto value = requireValue(index, values);
      if (value == "4")
        overrides.connectivity = Connectivity::Four;
      else if (value == "8")
        overrides.connectivity = Connectivity::Eight;
      else
        throw std::invalid_argument("Connectivity must be 4 or 8.");
    } else if (option == "--apply-high") {
      arguments.applyHigh = true;
    } else if (option == "--predictor") {
      const auto value = requireValue(index, values);
      if (value != "rule_based" && value != "onnx")
        throw std::invalid_argument("Predictor must be rule_based or onnx.");
      overrides.predictorOnnx = value == "onnx";
    } else if (option == "--no-highlight") {
      overrides.createHighlightLayer = false;
    } else if (option == "--debug") {
      overrides.debugLogging = true;
    } else if (option == "--force") {
      arguments.force = true;
    } else {
      throw std::invalid_argument("Unknown option: " + option);
    }
  }

  if (arguments.showHelp) return arguments;
  if (arguments.input.empty()) throw std::invalid_argument("--input is required.");
  if (!arguments.settingsPath.empty()) {
    if (!std::filesystem::is_regular_file(arguments.settingsPath))
      throw std::invalid_argument("Settings file does not exist: " +
                                  arguments.settingsPath.string());
    arguments.settings = SettingsStore::load(arguments.settingsPath);
  }
  applyOverrides(arguments.settings, overrides);

  const auto stem = arguments.input.parent_path() / arguments.input.stem();
  if (arguments.correction.empty()) arguments.correction = stem.string() + ".gap-corrections.png";
  if (arguments.highlight.empty()) arguments.highlight = stem.string() + ".gap-highlights.png";
  if (arguments.corrected.empty()) arguments.corrected = stem.string() + ".gap-corrected.png";
  if (arguments.manifest.empty()) arguments.manifest = stem.string() + ".gap-manifest.json";
  if (arguments.contactSheet.empty()) arguments.contactSheet = stem.string() + ".gap-review.png";
  return arguments;
}

}  // namespace gap_assist
