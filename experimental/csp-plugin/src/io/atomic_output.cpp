#include "io/atomic_output.hpp"

#include <exception>
#include <fstream>
#include <random>
#include <stdexcept>
#include <system_error>

namespace gap_assist {
namespace {

struct StagedOutput {
  const OutputFile* output{};
  std::filesystem::path temporary;
  std::filesystem::path backup;
  bool hadOriginal{};
  bool originalMoved{};
  bool installed{};
};

std::filesystem::path normalizedIdentity(const std::filesystem::path& path) {
  std::error_code error;
  auto absolute = std::filesystem::absolute(path, error);
  if (error)
    throw std::runtime_error("Cannot resolve path " + path.string() + ": " +
                             error.message());
  absolute = absolute.lexically_normal();
  auto canonical = std::filesystem::weakly_canonical(absolute, error);
  return error ? absolute : canonical.lexically_normal();
}

bool entryExists(const std::filesystem::path& path) {
  std::error_code error;
  const auto status = std::filesystem::symlink_status(path, error);
  if (error == std::errc::no_such_file_or_directory) return false;
  if (error)
    throw std::runtime_error("Cannot inspect path " + path.string() + ": " +
                             error.message());
  return status.type() != std::filesystem::file_type::not_found;
}

bool aliases(const std::filesystem::path& left, const std::filesystem::path& right) {
  const bool leftExists = entryExists(left);
  const bool rightExists = entryExists(right);
  if (leftExists && rightExists) {
    std::error_code error;
    const bool equivalent = std::filesystem::equivalent(left, right, error);
    if (error)
      throw std::runtime_error("Cannot compare filesystem paths: " + error.message());
    if (equivalent) return true;
  }
  return normalizedIdentity(left) == normalizedIdentity(right);
}

std::filesystem::path uniqueSibling(const std::filesystem::path& destination,
                                    const char* suffix) {
  std::random_device random;
  const auto directory = destination.has_parent_path()
                             ? destination.parent_path()
                             : std::filesystem::path(".");
  for (int attempt = 0; attempt < 128; ++attempt) {
    const auto candidate =
        directory /
        ("." + destination.filename().string() + ".gap-assist-" + suffix + "-" +
         std::to_string(random()) + "-" + std::to_string(attempt));
    if (!entryExists(candidate)) return candidate;
  }
  throw std::runtime_error("Cannot allocate a temporary path beside " +
                           destination.string());
}

void removeIfPresent(const std::filesystem::path& path) noexcept {
  if (path.empty()) return;
  std::error_code ignored;
  std::filesystem::remove(path, ignored);
}

void rollback(std::vector<StagedOutput>& staged) {
  std::string failure;
  for (auto& item : staged) {
    if (!item.installed) continue;
    std::error_code error;
    std::filesystem::remove(item.output->path, error);
    if (error && failure.empty()) failure = error.message();
    item.installed = false;
  }
  for (auto& item : staged) {
    if (!item.originalMoved) continue;
    std::error_code error;
    std::filesystem::rename(item.backup, item.output->path, error);
    if (error && failure.empty()) failure = error.message();
    if (!error) item.originalMoved = false;
  }
  for (auto& item : staged) removeIfPresent(item.temporary);
  if (!failure.empty())
    throw std::runtime_error("Output rollback was incomplete: " + failure);
}

void invoke(const OutputFailureHook& hook, OutputCommitStage stage,
            const std::filesystem::path& path) {
  if (hook) hook(stage, path);
}

}  // namespace

void validateOutputPlan(const std::filesystem::path& input,
                        const std::vector<OutputFile>& outputs, bool force) {
  if (input.empty()) throw std::invalid_argument("Input path is required.");
  if (!entryExists(input))
    throw std::invalid_argument("Input does not exist: " + input.string());
  for (std::size_t index = 0; index < outputs.size(); ++index) {
    const auto& output = outputs[index];
    if (output.path.empty())
      throw std::invalid_argument("Output path is empty for role " + output.role);
    if (aliases(input, output.path))
      throw std::invalid_argument("Output " + output.role +
                                  " aliases the input source.");
    for (std::size_t prior = 0; prior < index; ++prior) {
      if (aliases(outputs[prior].path, output.path))
        throw std::invalid_argument("Output roles " + outputs[prior].role + " and " +
                                    output.role + " alias the same file.");
    }
    if (!force && entryExists(output.path))
      throw std::invalid_argument("Output already exists (use --force): " +
                                  output.path.string());
  }
}

void commitOutputPlan(const std::filesystem::path& input,
                      const std::vector<OutputFile>& outputs, bool force,
                      const OutputFailureHook& failureHook) {
  validateOutputPlan(input, outputs, force);
  std::vector<StagedOutput> staged;
  staged.reserve(outputs.size());
  try {
    for (const auto& output : outputs) {
      if (output.path.has_parent_path())
        std::filesystem::create_directories(output.path.parent_path());
      staged.push_back({});
      auto& item = staged.back();
      item.output = &output;
      item.hadOriginal = entryExists(output.path);
      if (item.hadOriginal && !force)
        throw std::invalid_argument("Output already exists (use --force): " +
                                    output.path.string());
      item.temporary = uniqueSibling(output.path, "tmp");
      if (item.hadOriginal) item.backup = uniqueSibling(output.path, "backup");
      invoke(failureHook, OutputCommitStage::TemporaryWrite, output.path);
      std::ofstream stream(item.temporary,
                           std::ios::binary | std::ios::out | std::ios::trunc);
      if (!stream)
        throw std::runtime_error("Cannot stage output: " + output.path.string());
      stream.write(reinterpret_cast<const char*>(output.bytes.data()),
                   static_cast<std::streamsize>(output.bytes.size()));
      stream.close();
      if (!stream)
        throw std::runtime_error("Cannot stage output: " + output.path.string());
    }

    for (auto& item : staged) {
      if (!item.hadOriginal) continue;
      invoke(failureHook, OutputCommitStage::BackupRename, item.output->path);
      std::filesystem::rename(item.output->path, item.backup);
      item.originalMoved = true;
    }
    for (auto& item : staged) {
      invoke(failureHook, OutputCommitStage::FinalRename, item.output->path);
      std::filesystem::rename(item.temporary, item.output->path);
      item.installed = true;
    }

    invoke(failureHook, OutputCommitStage::Cleanup, {});
    for (auto& item : staged) {
      if (!item.originalMoved) continue;
      std::error_code error;
      std::filesystem::remove(item.backup, error);
      if (!error) item.originalMoved = false;
    }
  } catch (...) {
    const auto original = std::current_exception();
    rollback(staged);
    std::rethrow_exception(original);
  }
}

}  // namespace gap_assist
