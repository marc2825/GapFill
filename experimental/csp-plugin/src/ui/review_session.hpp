#pragma once

#include <cstddef>
#include <optional>
#include <span>
#include <vector>

#include "core/image_types.hpp"

namespace gap_assist {

struct ReviewSummary {
  std::size_t detected{};
  std::size_t high{};
  std::size_t medium{};
  std::size_t low{};
  std::size_t apply{};
  std::size_t skip{};
  std::size_t markOnly{};
};

class ReviewSession {
 public:
  ReviewSession(std::vector<GapCandidate> gaps, RunMode mode);

  [[nodiscard]] const std::vector<GapCandidate>& gaps() const noexcept { return gaps_; }
  [[nodiscard]] std::vector<GapCandidate>& gaps() noexcept { return gaps_; }
  [[nodiscard]] RunMode mode() const noexcept { return mode_; }
  [[nodiscard]] ReviewSummary summary() const;

  bool setApply(int gapId, bool apply);
  bool skip(int gapId);
  bool markOnly(int gapId);
  void applySelected(std::span<const int> ids);
  void skipSelected(std::span<const int> ids);
  void applyHighConfidence();
  void applyAllRemainingHighConfidence();

  [[nodiscard]] std::size_t currentIndex() const noexcept { return currentIndex_; }
  [[nodiscard]] GapCandidate* current();
  [[nodiscard]] const GapCandidate* current() const;
  bool next();
  bool back();
  bool applyAndNext();
  bool skipAndNext();

 private:
  GapCandidate* find(int gapId);
  void initializeModeDefaults();

  std::vector<GapCandidate> gaps_;
  RunMode mode_;
  std::size_t currentIndex_{};
};

}  // namespace gap_assist
