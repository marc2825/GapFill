#include "core/owner_regions.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>

namespace gap_assist {
namespace {

constexpr std::int32_t kUnvisited = -2;
constexpr std::int32_t kQueued = -3;
constexpr std::array<Point, 4> kCardinal{{{-1, 0}, {1, 0}, {0, -1}, {0, 1}}};
constexpr std::array<Point, 4> kDiagonal{{{-1, -1}, {1, -1}, {-1, 1}, {1, 1}}};

int colorDifference(const Rgba& left, const Rgba& right) {
  return std::abs(static_cast<int>(left.r) - right.r) +
         std::abs(static_cast<int>(left.g) - right.g) +
         std::abs(static_cast<int>(left.b) - right.b);
}

}  // namespace

OwnerMap OwnerRegionDetector::detect(const Image& image, const Settings& settings,
                                     const SelectionMask* selection,
                                     const std::atomic_bool* cancelled,
                                     const ProgressCallback& progress) const {
  const int width = image.width();
  const int height = image.height();
  if (settings.scope == Scope::SelectionOnly &&
      (selection == nullptr || selection->width() != width ||
       selection->height() != height)) {
    throw std::invalid_argument(
        "Selection-only scope requires a mask matching the image dimensions.");
  }

  OwnerMap result{width, height,
                  std::vector<std::int32_t>(image.size(), kUnvisited), {}};
  std::vector<std::uint32_t> component;
  const auto inScope = [&](int x, int y) {
    return x >= 0 && y >= 0 && x < width && y < height &&
           (settings.scope != Scope::SelectionOnly ||
            (selection != nullptr && selection->selected(x, y)));
  };
  const auto opaque = [&](int x, int y) {
    return inScope(x, y) && image.at(x, y).a > settings.alphaThreshold;
  };

  for (int y = 0; y < height; ++y) {
    if (cancelled != nullptr && cancelled->load())
      throw std::runtime_error("Owner-region detection cancelled.");
    for (int x = 0; x < width; ++x) {
      const auto seed = static_cast<std::size_t>(y) * static_cast<std::size_t>(width) +
                        static_cast<std::size_t>(x);
      if (result.labels[seed] != kUnvisited) continue;
      if (!opaque(x, y)) {
        result.labels[seed] = -1;
        continue;
      }

      component.clear();
      component.push_back(static_cast<std::uint32_t>(seed));
      result.labels[seed] = kQueued;
      std::size_t cursor = 0;
      std::uint64_t red = 0;
      std::uint64_t green = 0;
      std::uint64_t blue = 0;
      int minX = std::numeric_limits<int>::max();
      int minY = std::numeric_limits<int>::max();
      int maxX = -1;
      int maxY = -1;

      while (cursor < component.size()) {
        if (cancelled != nullptr && (cursor & 0xffffU) == 0 && cancelled->load())
          throw std::runtime_error("Owner-region detection cancelled.");
        const auto flat = component[cursor++];
        const int currentX = static_cast<int>(flat % static_cast<std::uint32_t>(width));
        const int currentY = static_cast<int>(flat / static_cast<std::uint32_t>(width));
        const auto currentColor = image.atIndex(flat);
        red += currentColor.r;
        green += currentColor.g;
        blue += currentColor.b;
        minX = std::min(minX, currentX);
        minY = std::min(minY, currentY);
        maxX = std::max(maxX, currentX);
        maxY = std::max(maxY, currentY);

        const auto enqueue = [&](int nextX, int nextY) {
          if (!opaque(nextX, nextY)) return;
          const auto next = static_cast<std::size_t>(nextY) *
                                static_cast<std::size_t>(width) +
                            static_cast<std::size_t>(nextX);
          if (result.labels[next] != kUnvisited ||
              colorDifference(currentColor, image.atIndex(next)) >
                  settings.ownerColorTolerance) {
            return;
          }
          result.labels[next] = kQueued;
          component.push_back(static_cast<std::uint32_t>(next));
        };
        for (const auto offset : kCardinal)
          enqueue(currentX + offset.x, currentY + offset.y);
        if (settings.connectivity == Connectivity::Eight) {
          for (const auto offset : kDiagonal)
            enqueue(currentX + offset.x, currentY + offset.y);
        }
      }

      if (component.size() <= settings.gapThreshold) {
        for (const auto flat : component) result.labels[flat] = -1;
        continue;
      }
      const auto ownerId = static_cast<int>(result.regions.size());
      const double area = static_cast<double>(component.size());
      OwnerRegion owner;
      owner.id = ownerId;
      owner.area = component.size();
      owner.bbox = {minX, minY, maxX - minX + 1, maxY - minY + 1};
      owner.meanColor = {
          static_cast<std::uint8_t>(std::lround(static_cast<double>(red) / area)),
          static_cast<std::uint8_t>(std::lround(static_cast<double>(green) / area)),
          static_cast<std::uint8_t>(std::lround(static_cast<double>(blue) / area)),
          255};
      for (const auto flat : component) result.labels[flat] = ownerId;
      result.regions.push_back(owner);
    }
    if (progress && (y % 64 == 0 || y + 1 == height)) progress(y + 1, height);
  }

  return result;
}

}  // namespace gap_assist
