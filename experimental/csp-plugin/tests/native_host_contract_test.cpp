#include <algorithm>
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "plugin_entry/native_host_contract.hpp"

namespace {

using gap_assist::CanonicalInputSnapshot;
using gap_assist::CommitEvidence;
using gap_assist::HostCancelled;
using gap_assist::Image;
using gap_assist::MaskTile;
using gap_assist::NativeHostAdapter;
using gap_assist::NativeHostCapabilities;
using gap_assist::NativeHostSession;
using gap_assist::Rect;
using gap_assist::Rgba;
using gap_assist::RgbaTile;
using gap_assist::SelectionMask;
using gap_assist::SnapshotIdentity;

int failures = 0;
int checks = 0;

void check(bool condition, const std::string& message) {
  ++checks;
  if (!condition) {
    ++failures;
    std::cerr << "FAIL: " << message << '\n';
  }
}

template <typename Exception = std::exception, typename Function>
void checkThrows(Function&& function, const std::string& message) {
  ++checks;
  try {
    function();
  } catch (const Exception&) {
    return;
  } catch (...) {
  }
  ++failures;
  std::cerr << "FAIL: " << message << '\n';
}

RgbaTile rgbaTile(Rect bounds, std::vector<std::uint8_t> bytes,
                  std::size_t rowStride, std::size_t pixelStride = 4,
                  std::array<std::size_t, 4> rgbaOffsets = {0, 1, 2, 3}) {
  return RgbaTile{bounds, rowStride, pixelStride, rgbaOffsets, std::move(bytes)};
}

RgbaTile solidTile(Rect bounds, Rgba color) {
  std::vector<std::uint8_t> bytes(
      static_cast<std::size_t>(bounds.width) *
      static_cast<std::size_t>(bounds.height) * 4);
  for (std::size_t index = 0; index < bytes.size(); index += 4) {
    bytes[index] = color.r;
    bytes[index + 1] = color.g;
    bytes[index + 2] = color.b;
    bytes[index + 3] = color.a;
  }
  return rgbaTile(bounds, std::move(bytes),
                  static_cast<std::size_t>(bounds.width) * 4);
}

MaskTile maskTile(Rect bounds, std::vector<std::uint8_t> bytes,
                  std::size_t rowStride, std::size_t pixelStride = 1,
                  std::size_t valueOffset = 0) {
  return MaskTile{bounds, rowStride, pixelStride, valueOffset, std::move(bytes)};
}

CanonicalInputSnapshot snapshot(std::optional<SelectionMask> selection = std::nullopt) {
  const Rect document{11, -7, 3, 2};
  Image coloring(3, 2, Rgba{10, 20, 30, 255});
  coloring.at(1, 1).a = 0;
  Image line(3, 2, Rgba{});
  line.at(0, 1) = Rgba{1, 2, 3, 255};
  Image guide(3, 2, Rgba{});
  guide.at(2, 0) = Rgba{4, 5, 6, 255};
  return CanonicalInputSnapshot::fromNormalizedRasters(
      SnapshotIdentity{101, 202, 303}, document, std::move(coloring),
      std::move(line), std::move(guide), std::move(selection));
}

class FakeHost final : public NativeHostAdapter {
 public:
  NativeHostCapabilities capabilitiesValue{
      true, true, true, true, true, true, true, true, true};
  CanonicalInputSnapshot snapshotValue{snapshot()};
  SnapshotIdentity currentIdentity{snapshotValue.identity};
  bool cancelDuringAcquire{};
  bool cancelled{};
  bool throwDuringAcquire{};
  bool throwDuringPreview{};
  bool throwDuringStage{};
  bool cancelAfterStage{};
  bool staleAfterStage{};
  CommitEvidence evidence{true, true};
  int acquireCalls{};
  int replacePreviewCalls{};
  int discardPreviewCalls{};
  int beginCalls{};
  int stageCalls{};
  int commitCalls{};
  int abortCalls{};
  Image lastPreview;
  Image lastStaged;

  [[nodiscard]] NativeHostCapabilities capabilities() const override {
    return capabilitiesValue;
  }

  [[nodiscard]] CanonicalInputSnapshot acquireCanonicalInput(
      const std::function<bool()>& cancelRequested) override {
    ++acquireCalls;
    if (throwDuringAcquire) throw std::runtime_error("injected read failure");
    if (cancelDuringAcquire || cancelRequested()) throw HostCancelled{};
    return snapshotValue;
  }

  [[nodiscard]] bool snapshotStillCurrent(
      const SnapshotIdentity& identity) const override {
    return identity == currentIdentity && !(staleAfterStage && stageCalls != 0);
  }

  [[nodiscard]] bool cancellationRequested() const override {
    return cancelled || (cancelAfterStage && stageCalls != 0);
  }

  void replacePreview(const SnapshotIdentity&, const Image& pixels) override {
    ++replacePreviewCalls;
    if (throwDuringPreview) throw std::runtime_error("injected preview failure");
    lastPreview = pixels;
  }

  void discardPreview() noexcept override { ++discardPreviewCalls; }

  void beginFinalMutation(const SnapshotIdentity&) override { ++beginCalls; }

  void stageFinalPixels(const Image& pixels) override {
    ++stageCalls;
    if (throwDuringStage) throw std::runtime_error("injected stage failure");
    lastStaged = pixels;
  }

  [[nodiscard]] CommitEvidence commitFinalMutation() override {
    ++commitCalls;
    return evidence;
  }

  void abortFinalMutation() noexcept override { ++abortCalls; }
};

void testRasterAssembly() {
  {
    const Rect document{10, 20, 2, 1};
    const std::vector<std::uint8_t> bgraWithPadding{
        3, 2, 1, 4, 99, 88, 33, 22, 11, 44, 77, 66};
    const auto image = gap_assist::assembleNormalizedRgbaPlane(
        document, document,
        {rgbaTile(document, bgraWithPadding, 12, 6, {2, 1, 0, 3})});
    check(image.at(0, 0) == Rgba{1, 2, 3, 4},
          "asymmetric BGRA channel offsets are honored");
    check(image.at(1, 0) == Rgba{11, 22, 33, 44},
          "pixel and row padding are ignored");
  }

  {
    const Rect document{-3, 7, 5, 3};
    const Rect cropped{-1, 8, 3, 1};
    const auto image = gap_assist::assembleNormalizedRgbaPlane(
        document, cropped, {solidTile(cropped, Rgba{9, 8, 7, 6})});
    check(image.width() == 5 && image.height() == 3,
          "document dimensions survive nonzero origins");
    check(image.at(2, 1) == Rgba{9, 8, 7, 6},
          "cropped plane is positioned in document coordinates");
    check(image.at(0, 0) == Rgba{},
          "outside a cropped plane is transparent");
  }

  {
    const Rect document{4, 5, 3, 3};
    const Rect left{4, 5, 1, 3};
    const Rect right{5, 5, 2, 3};
    const auto image = gap_assist::assembleNormalizedRgbaPlane(
        document, document,
        {solidTile(right, Rgba{2, 0, 0, 255}),
         solidTile(left, Rgba{1, 0, 0, 255})});
    check(image.at(0, 2).r == 1 && image.at(2, 2).r == 2,
          "odd dimensions and out-of-order complete tiles assemble");
  }

  {
    const Rect onePixel{91, -22, 1, 1};
    const auto image = gap_assist::assembleNormalizedRgbaPlane(
        onePixel, onePixel, {solidTile(onePixel, Rgba{7, 6, 5, 4})});
    check(image.at(0, 0) == Rgba{7, 6, 5, 4},
          "one-pixel planes are valid");
  }

  {
    const Rect vertical{0, 0, 1, 3};
    const Rect horizontal{0, 0, 3, 1};
    check(gap_assist::assembleNormalizedRgbaPlane(
              vertical, vertical,
              {solidTile(vertical, Rgba{1, 2, 3, 4})})
              .height() == 3,
          "one-pixel-wide planes are valid");
    check(gap_assist::assembleNormalizedRgbaPlane(
              horizontal, horizontal,
              {solidTile(horizontal, Rgba{5, 6, 7, 8})})
              .width() == 3,
          "one-pixel-tall planes are valid");
  }

  {
    const Rect document{0, 0, 5, 1};
    const std::vector<std::uint8_t> alphaExtremes{
        9, 8, 7, 0, 9, 8, 7, 1, 9, 8, 7, 127,
        9, 8, 7, 254, 9, 8, 7, 255};
    const auto image = gap_assist::assembleNormalizedRgbaPlane(
        document, document, {rgbaTile(document, alphaExtremes, 20)});
    check(image.at(0, 0).a == 0 && image.at(1, 0).a == 1 &&
              image.at(2, 0).a == 127 && image.at(3, 0).a == 254 &&
              image.at(4, 0).a == 255,
          "all alpha extremes survive host layout assembly exactly");
  }
}

void testRasterAssemblyRejectsInvalidLayouts() {
  const Rect document{0, 0, 2, 2};
  checkThrows([&] {
    (void)gap_assist::assembleNormalizedRgbaPlane(
        document, document, {solidTile(Rect{0, 0, 2, 1}, Rgba{})});
  }, "missing tile coverage is rejected");
  checkThrows([&] {
    (void)gap_assist::assembleNormalizedRgbaPlane(
        document, document,
        {solidTile(document, Rgba{}), solidTile(Rect{0, 0, 1, 1}, Rgba{})});
  }, "overlapping tiles are rejected");
  checkThrows([&] {
    (void)gap_assist::assembleNormalizedRgbaPlane(
        document, Rect{-1, 0, 2, 2},
        {solidTile(Rect{-1, 0, 2, 2}, Rgba{})});
  }, "plane bounds outside the document are rejected");
  checkThrows([&] {
    (void)gap_assist::assembleNormalizedRgbaPlane(
        document, document,
        {rgbaTile(document, std::vector<std::uint8_t>(16), 7)});
  }, "short row strides are rejected");
  checkThrows([&] {
    (void)gap_assist::assembleNormalizedRgbaPlane(
        document, document,
        {rgbaTile(document, std::vector<std::uint8_t>(16), 8, 4,
                  {0, 1, 2, 4})});
  }, "channel offsets outside the pixel are rejected");
}

void testSelectionAssembly() {
  const Rect document{-2, -1, 3, 2};
  const Rect selected{-1, -1, 2, 2};
  const auto mask = gap_assist::assembleSelectionMask(
      document, selected,
      {maskTile(selected, {1, 99, 127, 99, 2, 99, 255, 99}, 4, 2)});
  check(mask.value(0, 0) == 0 && mask.value(1, 0) == 1 &&
            mask.value(2, 1) == 255,
        "selection origin, soft values, and interleaved padding are preserved");
  checkThrows([&] {
    (void)gap_assist::assembleSelectionMask(
        document, selected,
        {maskTile(Rect{-1, -1, 2, 1}, {1, 2}, 2)});
  }, "partial selection coverage is rejected");
}

void testCanonicalSnapshot() {
  SelectionMask selection(3, 2);
  selection.set(1, 1, 17);
  auto value = snapshot(selection);
  value.validate();
  check(value.geometry.coloringGap.value(1, 1),
        "Coloring alpha zero is normalized independently");
  check(value.geometry.lineBoundary.value(0, 1) &&
            !value.geometry.guideBoundary.value(0, 1),
        "Line boundary remains independent from Guide");
  check(value.geometry.guideBoundary.value(2, 0) &&
            !value.geometry.lineBoundary.value(2, 0),
        "Guide boundary remains independent from Line");
  check(value.selection->value(1, 1) == 17,
        "soft selection survives snapshot normalization");

  auto withoutSelection = snapshot();
  withoutSelection.validate();
  check(!withoutSelection.selection.has_value(),
        "absence of a host selection is represented explicitly");

  SelectionMask fullSelection(3, 2, 255);
  auto fullySelected = snapshot(fullSelection);
  check(fullySelected.selection->value(0, 0) == 255 &&
            fullySelected.selection->value(2, 1) == 255,
        "full selection remains distinct from absent selection");

  auto invalid = snapshot();
  invalid.lineArt = Image(2, 2);
  checkThrows([&] { invalid.validate(); },
              "mismatched source dimensions are rejected");

  invalid = snapshot();
  invalid.colorNormalization.sourceProfile.clear();
  checkThrows([&] { invalid.validate(); },
              "missing structured source-profile metadata is rejected");

  const Rect document{30, 40, 4, 3};
  auto coloring = gap_assist::assembleNormalizedRgbaPlane(
      document, document, {solidTile(document, Rgba{2, 3, 4, 255})});
  coloring.at(1, 1).a = 0;
  coloring.at(3, 0).a = 0;
  auto line = gap_assist::assembleNormalizedRgbaPlane(
      document, Rect{31, 41, 1, 1},
      {solidTile(Rect{31, 41, 1, 1}, Rgba{10, 20, 30, 255})});
  auto guide = gap_assist::assembleNormalizedRgbaPlane(
      document, Rect{33, 40, 1, 2},
      {solidTile(Rect{33, 40, 1, 2}, Rgba{40, 50, 60, 255})});
  auto croppedSources = CanonicalInputSnapshot::fromNormalizedRasters(
      SnapshotIdentity{7, 8, 9}, document, coloring, line, guide);
  check(croppedSources.geometry.lineBoundary.value(1, 1) &&
            croppedSources.geometry.guideBoundary.value(3, 0),
        "differing Line and Guide extents remain independent");
  check(croppedSources.geometry.coloringGap.value(1, 1) &&
            croppedSources.geometry.coloringGap.value(3, 0),
        "transparent Coloring membership remains present beneath boundaries");

  const auto empty = gap_assist::assembleNormalizedRgbaPlane(
      document, Rect{document.x, document.y, 0, 0}, {});
  auto emptySources = CanonicalInputSnapshot::fromNormalizedRasters(
      SnapshotIdentity{7, 8, 10}, document, coloring, empty, empty);
  check(std::none_of(emptySources.geometry.lineBoundary.values().begin(),
                     emptySources.geometry.lineBoundary.values().end(),
                     [](std::uint8_t value) { return value != 0; }) &&
            std::none_of(emptySources.geometry.guideBoundary.values().begin(),
                         emptySources.geometry.guideBoundary.values().end(),
                         [](std::uint8_t value) { return value != 0; }),
        "empty Line and Guide planes remain empty independent inputs");
}

void testCapabilityAndAcquisitionGates() {
  FakeHost host;
  NativeHostSession session(host);
  const auto acquired = session.acquire();
  check(acquired.identity == host.snapshotValue.identity && host.acquireCalls == 1,
        "complete canonical capability set permits acquisition");
  (void)session.acquire();
  check(host.acquireCalls == 2,
        "repeated invocation reacquires rather than reusing hidden state");

  host.capabilitiesValue.lineInput = false;
  checkThrows([&] { (void)session.acquire(); },
              "missing independent Line input fails closed");
  check(host.acquireCalls == 2,
        "failed capability preflight does not read host pixels");

  FakeHost cancelledHost;
  cancelledHost.cancelDuringAcquire = true;
  NativeHostSession cancelledSession(cancelledHost);
  checkThrows<HostCancelled>([&] { (void)cancelledSession.acquire(); },
                             "cancellation during acquisition is propagated");

  FakeHost failingHost;
  failingHost.throwDuringAcquire = true;
  NativeHostSession failingSession(failingHost);
  checkThrows([&] { (void)failingSession.acquire(); },
              "acquisition exceptions propagate without a host mutation");
  check(failingHost.beginCalls == 0 && failingHost.replacePreviewCalls == 0,
        "acquisition exceptions cannot write or preview");
}

void testPreviewLifecycle() {
  FakeHost host;
  NativeHostSession session(host);
  const auto acquired = session.acquire();
  Image preview(3, 2, Rgba{1, 2, 3, 4});
  session.replacePreview(acquired, preview);
  preview.at(0, 0).r = 9;
  session.replacePreview(acquired, preview);
  check(host.replacePreviewCalls == 2 && host.lastPreview.at(0, 0).r == 9,
        "settings restart replaces, rather than commits, preview state");
  session.cancelPreview();
  check(host.discardPreviewCalls == 1,
        "preview cancellation discards temporary output");

  host.currentIdentity.revision++;
  checkThrows([&] { session.replacePreview(acquired, preview); },
              "stale preview snapshots are rejected");

  FakeHost cancelledHost;
  NativeHostSession cancelledSession(cancelledHost);
  const auto cancelledSnapshot = cancelledSession.acquire();
  cancelledHost.cancelled = true;
  checkThrows<HostCancelled>(
      [&] { cancelledSession.replacePreview(cancelledSnapshot, preview); },
      "cancelled previews do not reach the host");
  check(cancelledHost.replacePreviewCalls == 0,
        "cancelled preview performs no replacement");

  FakeHost failingHost;
  failingHost.throwDuringPreview = true;
  NativeHostSession failingSession(failingHost);
  const auto failingSnapshot = failingSession.acquire();
  checkThrows([&] { failingSession.replacePreview(failingSnapshot, preview); },
              "preview replacement exceptions are propagated");
  check(failingHost.discardPreviewCalls == 1,
        "preview replacement exceptions discard partial temporary state");

  failingSession.cancelPreview();
  failingSession.cancelPreview();
  check(failingHost.discardPreviewCalls == 3,
        "close/dispose preview cleanup is repeatable and non-committing");
}

void testFinalMutationLifecycle() {
  const Image output(3, 2, Rgba{7, 8, 9, 255});

  {
    FakeHost host;
    NativeHostSession session(host);
    const auto acquired = session.acquire();
    session.commit(acquired, output);
    check(host.beginCalls == 1 && host.stageCalls == 1 &&
              host.commitCalls == 1 && host.abortCalls == 0,
          "successful final mutation has one begin/stage/commit sequence");
    check(host.lastStaged.at(0, 0) == output.at(0, 0) &&
              host.lastStaged.at(2, 1) == output.at(2, 1),
          "final OK stages exactly the intended output pixels");
  }

  {
    FakeHost host;
    NativeHostSession session(host);
    const auto acquired = session.acquire();
    host.currentIdentity.revision++;
    checkThrows([&] { session.commit(acquired, output); },
                "stale source is rejected before final mutation");
    check(host.beginCalls == 0, "stale commit writes nothing");
  }

  {
    FakeHost host;
    NativeHostSession session(host);
    const auto acquired = session.acquire();
    host.cancelled = true;
    checkThrows<HostCancelled>([&] { session.commit(acquired, output); },
                               "pre-commit cancellation is propagated");
    check(host.beginCalls == 0, "pre-commit cancellation writes nothing");
  }

  {
    FakeHost host;
    host.throwDuringStage = true;
    NativeHostSession session(host);
    const auto acquired = session.acquire();
    checkThrows([&] { session.commit(acquired, output); },
                "partial-write exception is propagated");
    check(host.abortCalls == 1 && host.commitCalls == 0,
          "partial-write exception aborts the transaction");
  }

  {
    FakeHost host;
    host.cancelAfterStage = true;
    NativeHostSession session(host);
    const auto acquired = session.acquire();
    checkThrows<HostCancelled>([&] { session.commit(acquired, output); },
                               "mid-write cancellation is propagated");
    check(host.abortCalls == 1 && host.commitCalls == 0,
          "mid-write cancellation aborts without commit");
  }

  {
    FakeHost host;
    host.staleAfterStage = true;
    NativeHostSession session(host);
    const auto acquired = session.acquire();
    checkThrows([&] { session.commit(acquired, output); },
                "source mutation during staging is rejected");
    check(host.abortCalls == 1 && host.commitCalls == 0,
          "source mutation during staging aborts without commit");
  }

  {
    FakeHost host;
    host.capabilitiesValue.atomicFinalMutation = false;
    NativeHostSession session(host);
    const auto acquired = session.acquire();
    checkThrows([&] { session.commit(acquired, output); },
                "missing atomic final-mutation capability fails closed");
    check(host.beginCalls == 0, "capability failure writes nothing");
  }

  {
    FakeHost host;
    host.evidence = CommitEvidence{false, true};
    NativeHostSession session(host);
    const auto acquired = session.acquire();
    checkThrows([&] { session.commit(acquired, output); },
                "commit without one-step Undo evidence is rejected");
  }

  {
    FakeHost host;
    host.evidence = CommitEvidence{true, false};
    NativeHostSession session(host);
    const auto acquired = session.acquire();
    checkThrows([&] { session.commit(acquired, output); },
                "commit without Redo evidence is rejected");
  }
}

}  // namespace

int main() {
  testRasterAssembly();
  testRasterAssemblyRejectsInvalidLayouts();
  testSelectionAssembly();
  testCanonicalSnapshot();
  testCapabilityAndAcquisitionGates();
  testPreviewLifecycle();
  testFinalMutationLifecycle();

  if (failures != 0) {
    std::cerr << failures << " of " << checks
              << " native-host contract checks failed.\n";
    return 1;
  }
  std::cout << checks << "/" << checks
            << " native-host contract checks passed.\n";
  return 0;
}
