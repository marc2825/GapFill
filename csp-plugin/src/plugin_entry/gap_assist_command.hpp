#pragma once

#include <string>

#include "core/settings.hpp"
#include "plugin_entry/host_filter_context.hpp"

namespace gap_assist {

enum class CommandStatus {
  Applied,
  Cancelled,
  NoGaps,
  UnsupportedSafeOutput,
  Failed,
};

struct CommandResult {
  CommandStatus status{CommandStatus::Failed};
  std::size_t detected{};
  std::size_t applied{};
  std::size_t marked{};
  std::string message;
};

class GapAssistCommand {
 public:
  [[nodiscard]] CommandResult run(HostFilterContext& host,
                                  const Settings& settings) const;
};

}  // namespace gap_assist
