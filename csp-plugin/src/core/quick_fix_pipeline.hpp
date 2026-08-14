#pragma once

#include <atomic>
#include <functional>

#include "core/gap_detection.hpp"
#include "core/image_types.hpp"
#include "core/settings.hpp"

namespace gap_assist {

struct QuickFixResult {
  Image correctedComposite;
  std::size_t detected{};
  std::size_t applied{};
  std::size_t high{};
  std::size_t medium{};
  std::size_t low{};
};

// Restricted-host pipeline for a conventional filter API. It applies only
// High-confidence predictions to an in-memory copy. The host remains responsible
// for Preview, OK/Cancel, committing destination pixels, and Undo.
class QuickFixPipeline {
 public:
  [[nodiscard]] QuickFixResult run(
      const Image& source, const DetectionGeometry& geometry, Settings settings,
      const SelectionMask* selection = nullptr,
      const std::atomic_bool* cancelled = nullptr,
      const ProgressCallback& progress = {},
      const std::function<void()>& cancellationPoll = {}) const;

  [[nodiscard]] QuickFixResult run(
      const Image& source, Settings settings,
      const SelectionMask* selection = nullptr,
      const std::atomic_bool* cancelled = nullptr,
      const ProgressCallback& progress = {},
      const std::function<void()>& cancellationPoll = {}) const;
};

}  // namespace gap_assist
