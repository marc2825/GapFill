#include "predictors/rule_based_predictor.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <unordered_map>

namespace gap_assist {
namespace {

struct Cluster {
  double weight{};
  double red{};
  double green{};
  double blue{};
  std::size_t samples{};
  double minimumDistance{std::numeric_limits<double>::infinity()};
  std::unordered_map<int, double> ownerWeights;
};

std::uint32_t colorBucket(const Rgba& color) {
  return (static_cast<std::uint32_t>(color.r >> 3) << 10U) |
         (static_cast<std::uint32_t>(color.g >> 3) << 5U) |
         static_cast<std::uint32_t>(color.b >> 3);
}

double distanceToRect(int x, int y, const Rect& rect) {
  const int dx = x < rect.x ? rect.x - x
                 : x >= rect.right() ? x - rect.right() + 1
                                     : 0;
  const int dy = y < rect.y ? rect.y - y
                 : y >= rect.bottom() ? y - rect.bottom() + 1
                                      : 0;
  return std::hypot(static_cast<double>(dx), static_cast<double>(dy));
}

}  // namespace

std::vector<PredictResult> RuleBasedPredictor::predict(const PredictInput& input) const {
  std::vector<PredictResult> results;
  results.reserve(input.gaps.size());
  const auto& image = input.image;
  const int radius = std::max(1, input.settings.samplingRadius);

  for (std::size_t gapIndex = 0; gapIndex < input.gaps.size(); ++gapIndex) {
    const auto& gap = input.gaps[gapIndex];
    if (input.cancellationPoll && (gapIndex & 0x3fU) == 0)
      input.cancellationPoll();
    if (input.cancelled != nullptr && input.cancelled->load())
      throw std::runtime_error("Color prediction cancelled.");
    std::unordered_map<std::uint32_t, Cluster> clusters;
    double totalWeight = 0.0;
    const int startX = std::max(0, gap.bbox.x - radius);
    const int startY = std::max(0, gap.bbox.y - radius);
    const int endX = std::min(image.width(), gap.bbox.right() + radius);
    const int endY = std::min(image.height(), gap.bbox.bottom() + radius);
    for (int y = startY; y < endY; ++y) {
      for (int x = startX; x < endX; ++x) {
        if (input.settings.scope == Scope::SelectionOnly &&
            (input.selection == nullptr || !input.selection->selected(x, y)))
          continue;
        const auto color = image.at(x, y);
        if (color.a <= input.settings.alphaThreshold) continue;
        const double distance = distanceToRect(x, y, gap.bbox);
        int owner = -1;
        if (input.owners != nullptr) owner = input.owners->ownerAt(x, y);
        // Prefer colors backed by a large connected owner without excluding
        // useful samples from small details when no owner reaches the gap.
        const double ownerBoost = owner >= 0 ? 1.35 : 1.0;
        const double weight =
            ownerBoost / (1.0 + std::max(0.0, distance - 1.0));
        auto& cluster = clusters[colorBucket(color)];
        cluster.weight += weight;
        cluster.red += weight * color.r;
        cluster.green += weight * color.g;
        cluster.blue += weight * color.b;
        ++cluster.samples;
        cluster.minimumDistance = std::min(cluster.minimumDistance, distance);
        if (owner >= 0) cluster.ownerWeights[owner] += weight;
        totalWeight += weight;
      }
    }

    PredictResult result;
    result.gapId = gap.id;
    if (clusters.empty() || totalWeight <= 0.0) {
      result.confidence = 0.0;
      result.debugInfo = "No opaque samples within the configured radius.";
      results.push_back(std::move(result));
      continue;
    }
    const auto best = std::max_element(
        clusters.begin(), clusters.end(),
        [](const auto& left, const auto& right) {
          return left.second.weight < right.second.weight;
        });
    const auto& cluster = best->second;
    result.suggestedColor = Rgba{
        static_cast<std::uint8_t>(std::clamp(std::lround(cluster.red / cluster.weight),
                                            0L, 255L)),
        static_cast<std::uint8_t>(std::clamp(
            std::lround(cluster.green / cluster.weight), 0L, 255L)),
        static_cast<std::uint8_t>(std::clamp(
            std::lround(cluster.blue / cluster.weight), 0L, 255L)),
        255};
    const double dominance = cluster.weight / totalWeight;
    const double expectedSamples = std::max(4.0, std::sqrt(static_cast<double>(gap.area)) * 4.0);
    const double support =
        std::min(1.0, static_cast<double>(cluster.samples) / expectedSamples);
    const double distancePenalty = cluster.minimumDistance <= 1.5
                                       ? 1.0
                                       : 1.0 / (1.0 + (cluster.minimumDistance - 1.0) * 0.15);
    result.confidence = std::clamp(dominance * (0.75 + 0.25 * support) * distancePenalty,
                                   0.0, 1.0);
    if (!cluster.ownerWeights.empty()) {
      const auto owner = std::max_element(
          cluster.ownerWeights.begin(), cluster.ownerWeights.end(),
          [](const auto& left, const auto& right) { return left.second < right.second; });
      result.sourceOwnerId = owner->first;
    }
    std::ostringstream debug;
    debug << "samples=" << cluster.samples << ", dominance=" << dominance
          << ", support=" << support << ", nearest=" << cluster.minimumDistance;
    result.debugInfo = debug.str();
    results.push_back(std::move(result));
  }
  return results;
}

}  // namespace gap_assist
