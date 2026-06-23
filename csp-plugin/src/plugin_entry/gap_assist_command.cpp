#include "plugin_entry/gap_assist_command.hpp"

#include <exception>
#include <optional>
#include <stdexcept>
#include <utility>

#include "core/correction_output.hpp"
#include "core/smart_gap_propagation.hpp"
#include "predictors/rule_based_predictor.hpp"

namespace gap_assist {

CommandResult GapAssistCommand::run(HostFilterContext& host,
                                    const Settings& requestedSettings) const {
  bool transactionOpen = false;
  try {
    Settings settings = requestedSettings;
    const auto capabilities = host.capabilities();
    const auto source = host.readActiveRasterLayer();
    if (source.empty()) throw std::runtime_error("The active raster layer is empty.");
    if (!capabilities.customReviewDialog) {
      return {CommandStatus::UnsupportedSafeOutput, 0, 0, 0,
              "This CSP SDK host cannot present the Gap Assist review dialog. No pixels "
              "were changed; use the PNG review harness instead."};
    }

    std::optional<SelectionMask> selection;
    if (settings.scope == Scope::SelectionOnly) {
      if (!capabilities.selectionRead) {
        throw std::runtime_error(
            "This CSP SDK host cannot read the current selection. Choose Whole Layer.");
      }
      selection = host.readSelectionMask();
      if (!selection.has_value())
        throw std::runtime_error("Selection Only was requested, but no selection exists.");
    }

    if (settings.predictorOnnx) {
      settings.predictorOnnx = false;
      host.showInformation(
          "The local ONNX adapter is not included in this build. Gap Assist will use "
          "Rule-Based prediction; the image remains on this device.");
    }
    RuleBasedPredictor predictor;
    SmartGapPropagation propagation;
    const auto progress = [&](std::size_t completed, std::size_t total) {
      host.reportProgress("Analyzing active layer", completed, total);
    };
    auto analysis = propagation.analyze(
        source, settings, predictor, selection.has_value() ? &*selection : nullptr,
        host.cancellationFlag(), progress);
    if (analysis.gaps.empty())
      return {CommandStatus::NoGaps, 0, 0, 0, "No enclosed gaps matched the settings."};

    ReviewSession review(std::move(analysis.gaps), settings.mode);
    if (!host.presentReviewDialog(review, source, settings)) {
      return {CommandStatus::Cancelled, review.gaps().size(), 0, 0,
              "Cancelled without modifying the document."};
    }
    CorrectionOutputGenerator generator;
    const auto output = generator.generate(
        source, review.gaps(), settings,
        settings.outputMode == OutputMode::OverwriteActiveLayer);

    if (settings.outputMode == OutputMode::CorrectionLayer &&
        !capabilities.createRasterLayer) {
      return {CommandStatus::UnsupportedSafeOutput,
              review.gaps().size(),
              0,
              output.markedCount,
              "The installed CSP filter SDK cannot create a Correction Layer. No pixels "
              "were changed. Export the correction PNG with the CLI or explicitly choose "
              "Overwrite Active Layer after duplicating the layer."};
    }
    if (settings.outputMode == OutputMode::OverwriteActiveLayer) {
      if (!capabilities.overwriteActiveLayer)
        return {CommandStatus::UnsupportedSafeOutput, review.gaps().size(), 0,
                output.markedCount,
                "This host cannot overwrite the active raster layer. No pixels changed."};
      if (!host.confirmOverwrite())
        return {CommandStatus::Cancelled, review.gaps().size(), 0, 0,
                "Overwrite cancelled without modifying the document."};
      if (!capabilities.undoTransaction)
        return {CommandStatus::UnsupportedSafeOutput, review.gaps().size(), 0,
                output.markedCount,
                "Overwrite is disabled because this host cannot guarantee a single Undo "
                "transaction. No pixels changed."};
    }

    if (capabilities.undoTransaction) {
      host.beginUndoTransaction("Gap Assist");
      transactionOpen = true;
    }
    if (settings.outputMode == OutputMode::CorrectionLayer) {
      host.createRasterLayer("Gap Assist Corrections", output.correctionLayer);
    } else {
      host.overwriteActiveLayer(output.correctedComposite);
    }
    if (settings.createHighlightLayer && output.markedCount > 0 &&
        capabilities.createRasterLayer) {
      host.createRasterLayer("Gap Assist Highlights", output.highlightLayer);
    }
    if (transactionOpen) {
      host.endUndoTransaction(true);
      transactionOpen = false;
    }
    return {CommandStatus::Applied, review.gaps().size(), output.appliedCount,
            output.markedCount, "Gap Assist output was applied."};
  } catch (const std::exception& error) {
    if (transactionOpen) host.endUndoTransaction(false);
    if (const auto* cancelled = host.cancellationFlag();
        cancelled != nullptr && cancelled->load()) {
      return {CommandStatus::Cancelled, 0, 0, 0,
              "Cancelled without modifying the document."};
    }
    host.showError(error.what());
    return {CommandStatus::Failed, 0, 0, 0, error.what()};
  }
}

}  // namespace gap_assist
