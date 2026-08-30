#include "core/gap_detection.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>
#include <utility>

namespace gap_assist {
namespace {

constexpr std::size_t kCancellationInterval = 4096;

struct Run {
  int start{};
  int end{};
  std::size_t component{};
};

struct Component {
  std::size_t area{};
  std::uint64_t sumX{};
  std::uint64_t sumY{};
  int minX{std::numeric_limits<int>::max()};
  int minY{std::numeric_limits<int>::max()};
  int maxX{-1};
  int maxY{-1};
  std::uint32_t firstPixel{std::numeric_limits<std::uint32_t>::max()};
  bool touchesEdge{};
  std::vector<std::uint32_t> pixels;
  std::vector<std::uint32_t> applicationPixels;
};

class UnionFind {
 public:
  explicit UnionFind(std::size_t size) : parent_(size), rank_(size, 0) {
    for (std::size_t index = 0; index < size; ++index) parent_[index] = index;
  }

  std::size_t find(std::size_t value) {
    std::size_t root = value;
    while (parent_[root] != root) root = parent_[root];
    while (parent_[value] != value) {
      const auto parent = parent_[value];
      parent_[value] = root;
      value = parent;
    }
    return root;
  }

  void unite(std::size_t left, std::size_t right) {
    left = find(left);
    right = find(right);
    if (left == right) return;
    if (rank_[left] < rank_[right]) std::swap(left, right);
    parent_[right] = left;
    if (rank_[left] == rank_[right]) ++rank_[left];
  }

 private:
  std::vector<std::size_t> parent_;
  std::vector<std::uint8_t> rank_;
};

void checkCancelled(const std::atomic_bool* cancelled) {
  if (cancelled != nullptr && cancelled->load())
    throw std::runtime_error("Gap detection cancelled.");
}

Component componentForRun(int y, int start, int end, int width, int height,
                          std::size_t threshold, const SelectionMask* selection,
                          Scope scope) {
  Component component;
  const auto length = static_cast<std::size_t>(end - start);
  component.area = length;
  component.sumX = static_cast<std::uint64_t>(start + end - 1) * length / 2U;
  component.sumY = static_cast<std::uint64_t>(y) * length;
  component.minX = start;
  component.minY = y;
  component.maxX = end - 1;
  component.maxY = y;
  component.firstPixel = static_cast<std::uint32_t>(
      static_cast<std::size_t>(y) * static_cast<std::size_t>(width) +
      static_cast<std::size_t>(start));
  component.touchesEdge =
      y == 0 || y + 1 == height || start == 0 || end == width;
  if (length <= threshold) {
    component.pixels.reserve(length);
    component.applicationPixels.reserve(length);
    for (int x = start; x < end; ++x) {
      const auto pixel = static_cast<std::uint32_t>(
          static_cast<std::size_t>(y) * static_cast<std::size_t>(width) +
          static_cast<std::size_t>(x));
      component.pixels.push_back(pixel);
      if (scope == Scope::SelectionOnly && selection != nullptr &&
          selection->selected(x, y)) {
        component.applicationPixels.push_back(pixel);
      }
    }
  }
  return component;
}

Component mergeComponents(Component left, Component right,
                          std::size_t threshold) {
  Component result;
  result.area = left.area + right.area;
  result.sumX = left.sumX + right.sumX;
  result.sumY = left.sumY + right.sumY;
  result.minX = std::min(left.minX, right.minX);
  result.minY = std::min(left.minY, right.minY);
  result.maxX = std::max(left.maxX, right.maxX);
  result.maxY = std::max(left.maxY, right.maxY);
  result.firstPixel = std::min(left.firstPixel, right.firstPixel);
  result.touchesEdge = left.touchesEdge || right.touchesEdge;
  if (result.area <= threshold) {
    if (left.pixels.size() < right.pixels.size()) std::swap(left, right);
    result.pixels = std::move(left.pixels);
    result.pixels.insert(result.pixels.end(), right.pixels.begin(), right.pixels.end());
    result.applicationPixels = std::move(left.applicationPixels);
    result.applicationPixels.insert(result.applicationPixels.end(),
                                    right.applicationPixels.begin(),
                                    right.applicationPixels.end());
  }
  return result;
}

struct CompletedCandidate {
  GapCandidate gap;
  std::uint32_t firstPixel{};
};

void finishComponent(Component component, std::size_t threshold, Scope scope,
                     std::vector<CompletedCandidate>& completed) {
  if (component.touchesEdge || component.area > threshold) return;
  if (scope == Scope::SelectionOnly && component.applicationPixels.empty()) return;
  std::sort(component.pixels.begin(), component.pixels.end());
  std::sort(component.applicationPixels.begin(), component.applicationPixels.end());
  GapCandidate gap;
  gap.pixels = std::move(component.pixels);
  gap.applicationPixels = std::move(component.applicationPixels);
  gap.area = component.area;
  gap.bbox = {component.minX, component.minY, component.maxX - component.minX + 1,
              component.maxY - component.minY + 1};
  // The frozen cross-language contract uses floor-of-mean integer centroids.
  gap.centroid = {
      static_cast<double>(component.sumX / component.area),
      static_cast<double>(component.sumY / component.area),
  };
  completed.push_back({std::move(gap), component.firstPixel});
}

}  // namespace

BinaryMask::BinaryMask(int width, int height, bool fill)
    : width_(width),
      height_(height),
      values_(Image(width, height).size(), static_cast<std::uint8_t>(fill ? 1 : 0)) {}

bool BinaryMask::value(int x, int y) const {
  if (x < 0 || y < 0 || x >= width_ || y >= height_) return false;
  const auto index = static_cast<std::size_t>(y) * static_cast<std::size_t>(width_) +
                     static_cast<std::size_t>(x);
  return values_[index] != 0;
}

bool BinaryMask::atIndex(std::size_t index) const {
  return values_.at(index) != 0;
}

void BinaryMask::set(int x, int y, bool value) {
  if (x < 0 || y < 0 || x >= width_ || y >= height_)
    throw std::out_of_range("Binary-mask coordinate is outside the mask.");
  const auto index = static_cast<std::size_t>(y) * static_cast<std::size_t>(width_) +
                     static_cast<std::size_t>(x);
  values_[index] = static_cast<std::uint8_t>(value ? 1 : 0);
}

void DetectionGeometry::validate() const {
  if (lineBoundary.width() != width() || lineBoundary.height() != height() ||
      guideBoundary.width() != width() || guideBoundary.height() != height()) {
    throw std::invalid_argument(
        "Line and Guide boundary dimensions must match Coloring membership.");
  }
}

DetectionGeometry normalizeCanonicalColoringGeometry(const Image& coloring) {
  return normalizeLegacyRgbaGeometry(coloring);
}

DetectionGeometry normalizeLegacyRgbaGeometry(const Image& coloring,
                                               const Image* lineArt,
                                               const Image* guides) {
  const auto dimensionsMatch = [&](const Image* image) {
    return image == nullptr ||
           (image->width() == coloring.width() && image->height() == coloring.height());
  };
  if (!dimensionsMatch(lineArt) || !dimensionsMatch(guides))
    throw std::invalid_argument(
        "Line and Guide RGBA dimensions must match the Coloring image.");

  DetectionGeometry geometry(coloring.width(), coloring.height());
  for (std::size_t index = 0; index < coloring.size(); ++index) {
    const int x =
        static_cast<int>(index % static_cast<std::size_t>(coloring.width()));
    const int y =
        static_cast<int>(index / static_cast<std::size_t>(coloring.width()));
    geometry.coloringGap.set(x, y, coloring.atIndex(index).a == 0);
    if (lineArt != nullptr)
      geometry.lineBoundary.set(x, y, lineArt->atIndex(index).a != 0);
    if (guides != nullptr)
      geometry.guideBoundary.set(x, y, guides->atIndex(index).a != 0);
  }
  return geometry;
}

std::vector<GapCandidate> GapDetector::detect(
    const Image& image, const Settings& settings, const SelectionMask* selection,
    const std::atomic_bool* cancelled, const ProgressCallback& progress) const {
  const auto geometry = normalizeCanonicalColoringGeometry(image);
  return detect(geometry, settings, selection, cancelled, progress);
}

std::vector<GapCandidate> GapDetector::detect(
    const DetectionGeometry& geometry, const Settings& settings,
    const SelectionMask* selection, const std::atomic_bool* cancelled,
    const ProgressCallback& progress) const {
  geometry.validate();
  if (geometry.size() == 0 || settings.gapThreshold == 0) return {};
  if (settings.scope == Scope::SelectionOnly &&
      (selection == nullptr || selection->width() != geometry.width() ||
       selection->height() != geometry.height())) {
    throw std::invalid_argument(
        "Selection-only scope requires a mask matching the detection geometry.");
  }

  const int width = geometry.width();
  const int height = geometry.height();
  const bool eightNeighbor = settings.connectivity == Connectivity::Eight;
  std::vector<Component> active;
  std::vector<Run> previous;
  std::vector<CompletedCandidate> completed;
  std::size_t operations = 0;

  const auto isCandidate = [&](int x, int y) {
    return geometry.coloringGap.value(x, y) &&
           !geometry.lineBoundary.value(x, y) &&
           !geometry.guideBoundary.value(x, y);
  };

  for (int y = 0; y < height; ++y) {
    checkCancelled(cancelled);
    std::vector<Run> current;
    for (int x = 0; x < width;) {
      ++operations;
      if (operations % kCancellationInterval == 0) checkCancelled(cancelled);
      if (!isCandidate(x, y)) {
        ++x;
        continue;
      }
      const int start = x;
      while (x < width && isCandidate(x, y)) {
        ++x;
        ++operations;
        if (operations % kCancellationInterval == 0) checkCancelled(cancelled);
      }
      current.push_back({start, x, active.size() + current.size()});
    }

    std::vector<Component> nodes = std::move(active);
    nodes.reserve(nodes.size() + current.size());
    for (const auto& run : current) {
      nodes.push_back(componentForRun(y, run.start, run.end, width, height,
                                     settings.gapThreshold, selection,
                                     settings.scope));
    }
    UnionFind unionFind(nodes.size());
    std::size_t previousIndex = 0;
    for (const auto& run : current) {
      while (previousIndex < previous.size() &&
             (eightNeighbor ? previous[previousIndex].end < run.start
                            : previous[previousIndex].end <= run.start)) {
        ++previousIndex;
      }
      std::size_t candidateIndex = previousIndex;
      while (candidateIndex < previous.size() &&
             (eightNeighbor ? previous[candidateIndex].start <= run.end
                            : previous[candidateIndex].start < run.end)) {
        unionFind.unite(previous[candidateIndex].component, run.component);
        ++candidateIndex;
        ++operations;
        if (operations % kCancellationInterval == 0) checkCancelled(cancelled);
      }
    }

    std::unordered_map<std::size_t, Component> aggregated;
    aggregated.reserve(nodes.size());
    for (std::size_t index = 0; index < nodes.size(); ++index) {
      const auto root = unionFind.find(index);
      const auto existing = aggregated.find(root);
      if (existing == aggregated.end()) {
        aggregated.emplace(root, std::move(nodes[index]));
      } else {
        existing->second = mergeComponents(std::move(existing->second),
                                           std::move(nodes[index]),
                                           settings.gapThreshold);
      }
      ++operations;
      if (operations % kCancellationInterval == 0) checkCancelled(cancelled);
    }

    std::unordered_set<std::size_t> currentRoots;
    currentRoots.reserve(current.size());
    for (const auto& run : current) currentRoots.insert(unionFind.find(run.component));
    for (auto& [root, component] : aggregated) {
      if (!currentRoots.contains(root))
        finishComponent(std::move(component), settings.gapThreshold,
                        settings.scope, completed);
    }

    std::unordered_map<std::size_t, std::size_t> rootToActive;
    rootToActive.reserve(currentRoots.size());
    std::vector<Component> nextActive;
    nextActive.reserve(currentRoots.size());
    std::vector<Run> nextCurrent;
    nextCurrent.reserve(current.size());
    for (const auto& run : current) {
      const auto root = unionFind.find(run.component);
      auto [position, inserted] = rootToActive.emplace(root, nextActive.size());
      if (inserted) nextActive.push_back(std::move(aggregated.at(root)));
      nextCurrent.push_back({run.start, run.end, position->second});
    }
    active = std::move(nextActive);
    previous = std::move(nextCurrent);
    if (progress && (y % 64 == 0 || y + 1 == height)) progress(y + 1, height);
  }

  checkCancelled(cancelled);
  for (auto& component : active)
    finishComponent(std::move(component), settings.gapThreshold, settings.scope,
                    completed);
  std::sort(completed.begin(), completed.end(),
            [](const CompletedCandidate& left, const CompletedCandidate& right) {
              return left.firstPixel < right.firstPixel;
            });
  std::vector<GapCandidate> gaps;
  gaps.reserve(completed.size());
  for (auto& candidate : completed) {
    candidate.gap.id = static_cast<int>(gaps.size());
    gaps.push_back(std::move(candidate.gap));
  }
  return gaps;
}

}  // namespace gap_assist
