#pragma once

#include <array>
#include <cstdint>

#include "core/image_types.hpp"
#include "core/settings.hpp"

namespace gap_assist {

using SnapshotFingerprint = std::array<std::uint64_t, 4>;

struct CandidateContext {
  int width{};
  int height{};
  SnapshotFingerprint sourceFingerprint{};
  SnapshotFingerprint selectionFingerprint{};
  bool hasSelection{};
  Scope scope{Scope::WholeLayer};
  Connectivity connectivity{Connectivity::Four};
  ConfidencePreset confidencePreset{ConfidencePreset::Balanced};
  std::size_t gapThreshold{};
  std::uint8_t alphaThreshold{};
  int samplingRadius{};
  int ownerColorTolerance{};
  bool predictorOnnx{};
};

[[nodiscard]] CandidateContext captureCandidateContext(
    const Image& source, const Settings& settings,
    const SelectionMask* selection = nullptr);
void validateCandidateContext(const CandidateContext& context, const Image& source,
                              const Settings& settings,
                              const SelectionMask* selection = nullptr);

}  // namespace gap_assist
