#include "io/review_artifacts.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>

namespace gap_assist {
namespace {

constexpr int kPreviewSource = 32;
constexpr int kPreviewScale = 2;
constexpr int kPreviewPixels = kPreviewSource * kPreviewScale;
constexpr int kTileWidth = kPreviewPixels * 2 + 8;
constexpr int kTileHeight = kPreviewPixels + 8;

Rgba checker(int x, int y) {
  const std::uint8_t value = ((x / 8 + y / 8) % 2) == 0 ? 215 : 175;
  return {value, value, value, 255};
}

Rgba composite(Rgba foreground, Rgba background) {
  const int alpha = foreground.a;
  const int inverse = 255 - alpha;
  return {static_cast<std::uint8_t>((foreground.r * alpha + background.r * inverse) /
                                   255),
          static_cast<std::uint8_t>((foreground.g * alpha + background.g * inverse) /
                                   255),
          static_cast<std::uint8_t>((foreground.b * alpha + background.b * inverse) /
                                   255),
          255};
}

Rgba bandColor(ConfidenceBand band) {
  if (band == ConfidenceBand::High) return {0, 190, 120, 255};
  if (band == ConfidenceBand::Medium) return {255, 190, 0, 255};
  return {235, 55, 55, 255};
}

std::string escapeJson(const std::string& value) {
  std::ostringstream output;
  for (const char character : value) {
    switch (character) {
      case '\\':
        output << "\\\\";
        break;
      case '"':
        output << "\\\"";
        break;
      case '\n':
        output << "\\n";
        break;
      case '\r':
        output << "\\r";
        break;
      case '\t':
        output << "\\t";
        break;
      default:
        if (static_cast<unsigned char>(character) < 0x20)
          output << "?";
        else
          output << character;
    }
  }
  return output.str();
}

}  // namespace

Image renderReviewContactSheet(const Image& source,
                               const std::vector<GapCandidate>& gaps, int columns) {
  columns = std::max(1, columns);
  const int rows = std::max(1, static_cast<int>((gaps.size() + columns - 1) / columns));
  Image sheet(columns * kTileWidth, rows * kTileHeight, {35, 35, 35, 255});
  for (std::size_t gapIndex = 0; gapIndex < gaps.size(); ++gapIndex) {
    const auto& gap = gaps[gapIndex];
    const int tileX = static_cast<int>(gapIndex % columns) * kTileWidth;
    const int tileY = static_cast<int>(gapIndex / columns) * kTileHeight;
    const int centerX = static_cast<int>(std::lround(gap.centroid.x));
    const int centerY = static_cast<int>(std::lround(gap.centroid.y));
    const int sourceX = centerX - kPreviewSource / 2;
    const int sourceY = centerY - kPreviewSource / 2;
    for (int previewY = 0; previewY < kPreviewSource; ++previewY) {
      for (int previewX = 0; previewX < kPreviewSource; ++previewX) {
        const int imageX = sourceX + previewX;
        const int imageY = sourceY + previewY;
        Rgba before{};
        if (imageX >= 0 && imageY >= 0 && imageX < source.width() &&
            imageY < source.height())
          before = source.at(imageX, imageY);
        Rgba after = before;
        if (gap.suggestedColor.has_value() && imageX >= gap.bbox.x &&
            imageY >= gap.bbox.y && imageX < gap.bbox.right() &&
            imageY < gap.bbox.bottom()) {
          const auto flat = static_cast<std::uint32_t>(imageY * source.width() + imageX);
          if (std::find(gap.pixels.begin(), gap.pixels.end(), flat) != gap.pixels.end())
            after = *gap.suggestedColor;
        }
        for (int sy = 0; sy < kPreviewScale; ++sy) {
          for (int sx = 0; sx < kPreviewScale; ++sx) {
            const int localX = previewX * kPreviewScale + sx;
            const int localY = previewY * kPreviewScale + sy;
            const auto background = checker(localX, localY);
            sheet.at(tileX + 2 + localX, tileY + 2 + localY) =
                composite(before, background);
            sheet.at(tileX + 6 + kPreviewPixels + localX, tileY + 2 + localY) =
                composite(after, background);
          }
        }
      }
    }
    const auto border = bandColor(gap.confidenceBand);
    for (int x = tileX; x < tileX + kTileWidth; ++x) {
      sheet.at(x, tileY) = border;
      sheet.at(x, tileY + kTileHeight - 1) = border;
    }
    for (int y = tileY; y < tileY + kTileHeight; ++y) {
      sheet.at(tileX, y) = border;
      sheet.at(tileX + kTileWidth - 1, y) = border;
    }
  }
  return sheet;
}

std::string serializeGapManifest(const ReviewSession& session, bool includeDebug) {
  std::ostringstream output;
  const auto summary = session.summary();
  output << "{\n  \"summary\": {\"detected\": " << summary.detected
         << ", \"high\": " << summary.high << ", \"medium\": " << summary.medium
         << ", \"low\": " << summary.low << "},\n  \"gaps\": [\n";
  for (std::size_t index = 0; index < session.gaps().size(); ++index) {
    const auto& gap = session.gaps()[index];
    output << "    {\"id\": " << gap.id << ", \"area\": " << gap.area
           << ", \"bbox\": [" << gap.bbox.x << ", " << gap.bbox.y << ", "
           << gap.bbox.width << ", " << gap.bbox.height << "], \"centroid\": ["
           << std::fixed << std::setprecision(3) << gap.centroid.x << ", "
           << gap.centroid.y << "], \"confidence\": " << gap.confidence
           << ", \"band\": \"" << toString(gap.confidenceBand)
           << "\", \"apply\": " << (gap.apply ? "true" : "false")
           << ", \"status\": \"" << toString(gap.status) << "\", \"color\": ";
    if (gap.suggestedColor.has_value()) {
      const auto color = *gap.suggestedColor;
      output << '[' << static_cast<int>(color.r) << ", " << static_cast<int>(color.g)
             << ", " << static_cast<int>(color.b) << ", "
             << static_cast<int>(color.a) << ']';
    } else {
      output << "null";
    }
    output << ", \"sourceOwnerId\": ";
    if (gap.sourceOwnerId.has_value())
      output << *gap.sourceOwnerId;
    else
      output << "null";
    if (includeDebug)
      output << ", \"debug\": \"" << escapeJson(gap.debugInfo) << "\"";
    output << '}';
    if (index + 1 != session.gaps().size()) output << ',';
    output << '\n';
  }
  output << "  ]\n}\n";
  return output.str();
}

void writeGapManifest(const std::filesystem::path& path,
                      const ReviewSession& session, bool includeDebug) {
  if (path.has_parent_path()) std::filesystem::create_directories(path.parent_path());
  std::ofstream output(path, std::ios::trunc);
  if (!output) throw std::runtime_error("Cannot write manifest: " + path.string());
  output << serializeGapManifest(session, includeDebug);
  if (!output) throw std::runtime_error("Cannot write manifest: " + path.string());
}

void applyDecisionFile(const std::filesystem::path& path, ReviewSession& session) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("Cannot read decisions: " + path.string());
  std::unordered_map<int, std::string> decisions;
  for (std::string line; std::getline(input, line);) {
    if (line.empty() || line[0] == '#') continue;
    const auto separator = line.find('=');
    if (separator == std::string::npos)
      throw std::runtime_error("Invalid decision line: " + line);
    const int id = std::stoi(line.substr(0, separator));
    const std::string decision = line.substr(separator + 1);
    if (const auto found = decisions.find(id); found != decisions.end()) {
      if (found->second != decision)
        throw std::runtime_error("Conflicting duplicate decision for gap " +
                                 std::to_string(id));
      continue;
    }
    decisions.emplace(id, decision);
    bool accepted = false;
    if (decision == "apply") accepted = session.setApply(id, true);
    if (decision == "skip") accepted = session.skip(id);
    if (decision == "mark_only") accepted = session.markOnly(id);
    if (decision == "unreviewed") accepted = session.setApply(id, false);
    if (!accepted) throw std::runtime_error("Unknown gap or decision: " + line);
  }
}

}  // namespace gap_assist
