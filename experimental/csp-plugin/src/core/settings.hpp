#pragma once

#include <cstdint>
#include <filesystem>
#include <string>

#include "core/image_types.hpp"

namespace gap_assist {

enum class ConfidencePreset { Conservative, Balanced, Aggressive };
enum class GapSizePreset { Small, Medium, Large, Custom };

struct ConfidenceThresholds {
  double high{0.85};
  double medium{0.55};
};

struct Settings {
  RunMode mode{RunMode::ReviewList};
  OutputMode outputMode{OutputMode::CorrectionLayer};
  Scope scope{Scope::WholeLayer};
  Connectivity connectivity{Connectivity::Four};
  ConfidencePreset confidencePreset{ConfidencePreset::Balanced};
  GapSizePreset gapSizePreset{GapSizePreset::Medium};
  std::size_t gapThreshold{10};
  std::size_t customGapThreshold{10};
  std::uint8_t alphaThreshold{0};
  int samplingRadius{5};
  int ownerColorTolerance{30};
  bool createHighlightLayer{true};
  bool highlightHighConfidence{false};
  bool predictorOnnx{false};
  bool debugLogging{false};
};

[[nodiscard]] ConfidenceThresholds thresholdsFor(ConfidencePreset preset);
[[nodiscard]] ConfidenceBand classifyConfidence(double confidence,
                                                ConfidencePreset preset);
[[nodiscard]] std::string serializeSettings(const Settings& settings);

class SettingsStore {
 public:
  [[nodiscard]] static Settings load(const std::filesystem::path& path);
  static void save(const std::filesystem::path& path, const Settings& settings);
};

}  // namespace gap_assist
