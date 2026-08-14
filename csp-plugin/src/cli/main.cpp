#include <atomic>
#include <cstdint>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#include "cli/arguments.hpp"
#include "core/correction_output.hpp"
#include "core/smart_gap_propagation.hpp"
#include "io/atomic_output.hpp"
#include "io/png_io.hpp"
#include "io/review_artifacts.hpp"
#include "predictors/rule_based_predictor.hpp"
#include "ui/review_session.hpp"

namespace {

std::vector<std::uint8_t> bytesOf(const std::string& value) {
  return {value.begin(), value.end()};
}

std::vector<gap_assist::OutputFile> outputPlan(
    const gap_assist::CliArguments& arguments) {
  std::vector<gap_assist::OutputFile> outputs{
      {"correction", arguments.correction, {}},
      {"corrected", arguments.corrected, {}},
      {"manifest", arguments.manifest, {}},
      {"contact-sheet", arguments.contactSheet, {}},
  };
  if (arguments.settings.createHighlightLayer)
    outputs.push_back({"highlight", arguments.highlight, {}});
  if (!arguments.saveSettingsPath.empty())
    outputs.push_back({"save-settings", arguments.saveSettingsPath, {}});
  return outputs;
}

gap_assist::OutputFile& findRole(std::vector<gap_assist::OutputFile>& outputs,
                                 const std::string& role) {
  for (auto& output : outputs) {
    if (output.role == role) return output;
  }
  throw std::logic_error("Missing output role: " + role);
}

}  // namespace

int main(int argc, char** argv) {
  try {
    std::vector<std::string> values;
    values.reserve(static_cast<std::size_t>(argc > 0 ? argc - 1 : 0));
    for (int index = 1; index < argc; ++index) values.emplace_back(argv[index]);
    auto arguments = gap_assist::parseCliArguments(values);
    if (arguments.showHelp) {
      gap_assist::printCliUsage(std::cout);
      return 0;
    }

    auto outputFiles = outputPlan(arguments);
    gap_assist::validateOutputPlan(arguments.input, outputFiles, arguments.force);

    if (arguments.settings.predictorOnnx) {
      throw std::runtime_error(
          "This CSP build has no ONNX Runtime adapter; learned prediction was not "
          "run. Choose --predictor rule_based explicitly to use the uncalibrated "
          "heuristic fallback, which is never applied by --apply-high.");
    }
    const auto source = gap_assist::loadPng(arguments.input);
    std::optional<gap_assist::SelectionMask> selection;
    if (!arguments.selection.empty())
      selection = gap_assist::loadSelectionPng(arguments.selection, source.width(),
                                                source.height());

    gap_assist::RuleBasedPredictor predictor;
    gap_assist::SmartGapPropagation propagation;
    std::atomic_bool cancelled{false};
    auto result = propagation.analyze(
        source, arguments.settings, predictor,
        selection.has_value() ? &*selection : nullptr, &cancelled,
        [](std::size_t completed, std::size_t total) {
          if (completed == total) std::cerr << ".";
        });
    std::cerr << '\n';
    const auto context = result.candidateContext;
    gap_assist::ReviewSession review(std::move(result.gaps), arguments.settings.mode);
    if (!arguments.decisions.empty())
      gap_assist::applyDecisionFile(arguments.decisions, review);
    if (arguments.applyHigh) review.applyHighConfidence();

    const auto generated = gap_assist::CorrectionOutputGenerator().generate(
        source, review.gaps(), arguments.settings, context,
        selection.has_value() ? &*selection : nullptr);
    findRole(outputFiles, "correction").bytes =
        gap_assist::encodePng(generated.correctionLayer);
    findRole(outputFiles, "corrected").bytes =
        gap_assist::encodePng(generated.correctedComposite);
    findRole(outputFiles, "contact-sheet").bytes = gap_assist::encodePng(
        gap_assist::renderReviewContactSheet(source, review.gaps()));
    findRole(outputFiles, "manifest").bytes = bytesOf(gap_assist::serializeGapManifest(
        review, arguments.settings.debugLogging));
    if (arguments.settings.createHighlightLayer)
      findRole(outputFiles, "highlight").bytes =
          gap_assist::encodePng(generated.highlightLayer);
    if (!arguments.saveSettingsPath.empty())
      findRole(outputFiles, "save-settings").bytes =
          bytesOf(gap_assist::serializeSettings(arguments.settings));

    gap_assist::commitOutputPlan(arguments.input, outputFiles, arguments.force);

    const auto summary = review.summary();
    std::cout << "Detected gaps: " << summary.detected << " (high=" << summary.high
              << ", medium=" << summary.medium << ", low=" << summary.low << ")\n"
              << "Applied: " << generated.appliedCount
              << ", highlighted: " << generated.markedCount << '\n';
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "Gap Assist error: " << error.what() << '\n';
    return 1;
  }
}
