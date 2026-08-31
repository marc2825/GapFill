#pragma once

#include <cstdint>
#include <filesystem>
#include <functional>
#include <string>
#include <vector>

namespace gap_assist {

struct OutputFile {
  std::string role;
  std::filesystem::path path;
  std::vector<std::uint8_t> bytes;
};

enum class OutputCommitStage {
  TemporaryWrite,
  BackupRename,
  FinalRename,
  Cleanup,
};

using OutputFailureHook =
    std::function<void(OutputCommitStage, const std::filesystem::path&)>;

void validateOutputPlan(const std::filesystem::path& input,
                        const std::vector<OutputFile>& outputs, bool force);
void commitOutputPlan(const std::filesystem::path& input,
                      const std::vector<OutputFile>& outputs, bool force,
                      const OutputFailureHook& failureHook = {});

}  // namespace gap_assist
