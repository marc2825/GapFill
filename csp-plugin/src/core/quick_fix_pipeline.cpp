#include "core/quick_fix_pipeline.hpp"

#include <utility>

#include "core/correction_output.hpp"
#include "core/smart_gap_propagation.hpp"
#include "predictors/rule_based_predictor.hpp"
#include "ui/review_session.hpp"

namespace gap_assist {

QuickFixResult QuickFixPipeline::run(
    const Image& source, Settings settings, const SelectionMask* selection,
    const std::atomic_bool* cancelled, const ProgressCallback& progress,
    const std::function<void()>& cancellationPoll) const {
  settings.mode = RunMode::QuickFix;
  settings.outputMode = OutputMode::OverwriteActiveLayer;
  settings.createHighlightLayer = false;
  settings.highlightHighConfidence = false;
  if (selection != nullptr) settings.scope = Scope::SelectionOnly;

  RuleBasedPredictor predictor;
  auto analysis = SmartGapPropagation().analyze(
      source, settings, predictor, selection, cancelled, progress,
      cancellationPoll);
  ReviewSession review(std::move(analysis.gaps), RunMode::QuickFix);
  const auto summary = review.summary();
  auto output = CorrectionOutputGenerator().generate(
      source, review.gaps(), settings, analysis.candidateContext, selection, true);
  return {std::move(output.correctedComposite), summary.detected,
          output.appliedCount, summary.high, summary.medium, summary.low};
}

}  // namespace gap_assist
