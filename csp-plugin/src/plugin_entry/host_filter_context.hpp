#pragma once

#include <atomic>
#include <functional>
#include <optional>
#include <string>

#include "core/correction_output.hpp"
#include "core/image_types.hpp"
#include "core/settings.hpp"
#include "ui/review_session.hpp"

namespace gap_assist {

struct HostCapabilities {
  bool selectionRead{};
  bool createRasterLayer{};
  bool overwriteActiveLayer{};
  bool customReviewDialog{};
  bool undoTransaction{};
};

class HostFilterContext {
 public:
  virtual ~HostFilterContext() = default;

  [[nodiscard]] virtual HostCapabilities capabilities() const = 0;
  [[nodiscard]] virtual Image readActiveRasterLayer() = 0;
  [[nodiscard]] virtual std::optional<SelectionMask> readSelectionMask() = 0;
  [[nodiscard]] virtual bool presentReviewDialog(ReviewSession& session,
                                                 const Image& source,
                                                 const Settings& settings) = 0;
  [[nodiscard]] virtual bool confirmOverwrite() = 0;
  virtual void reportProgress(const std::string& stage, std::size_t completed,
                              std::size_t total) = 0;
  [[nodiscard]] virtual std::atomic_bool* cancellationFlag() = 0;

  virtual void beginUndoTransaction(const std::string& name) = 0;
  virtual void createRasterLayer(const std::string& name, const Image& pixels) = 0;
  virtual void overwriteActiveLayer(const Image& pixels) = 0;
  virtual void endUndoTransaction(bool commit) = 0;
  virtual void showError(const std::string& message) = 0;
  virtual void showInformation(const std::string& message) = 0;
};

}  // namespace gap_assist
