#pragma once

#include <filesystem>
#include <iosfwd>
#include <span>
#include <string>

#include "core/settings.hpp"

namespace gap_assist {

struct CliArguments {
  std::filesystem::path input;
  std::filesystem::path correction;
  std::filesystem::path highlight;
  std::filesystem::path corrected;
  std::filesystem::path manifest;
  std::filesystem::path contactSheet;
  std::filesystem::path selection;
  std::filesystem::path decisions;
  std::filesystem::path settingsPath;
  std::filesystem::path saveSettingsPath;
  Settings settings;
  bool applyHigh{};
  bool force{};
  bool showHelp{};
};

void printCliUsage(std::ostream& output);
[[nodiscard]] CliArguments parseCliArguments(std::span<const std::string> values);

}  // namespace gap_assist
