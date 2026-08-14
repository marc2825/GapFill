#include "core/candidate_context.hpp"

#include <cstddef>
#include <stdexcept>
#include <type_traits>

namespace gap_assist {
namespace {

class FingerprintBuilder {
 public:
  FingerprintBuilder()
      : values_{1469598103934665603ULL, 1099511628211ULL,
                7809847782465536322ULL, 9650029242287828579ULL} {}

  void addByte(std::uint8_t value) {
    constexpr std::array<std::uint64_t, 4> primes{
        1099511628211ULL, 14029467366897019727ULL, 1609587929392839161ULL,
        9650029242287828579ULL};
    for (std::size_t index = 0; index < values_.size(); ++index) {
      values_[index] ^= static_cast<std::uint64_t>(value) + index;
      values_[index] *= primes[index];
      values_[index] ^= values_[index] >> (13 + index);
    }
  }

  template <typename Value>
  void add(Value value) {
    static_assert(std::is_integral_v<Value> || std::is_enum_v<Value>);
    if constexpr (std::is_enum_v<Value>) {
      add(static_cast<std::underlying_type_t<Value>>(value));
    } else {
      using Unsigned = std::make_unsigned_t<Value>;
      const auto raw = static_cast<Unsigned>(value);
      for (std::size_t index = 0; index < sizeof(raw); ++index)
        addByte(static_cast<std::uint8_t>(raw >> (index * 8U)));
    }
  }

  [[nodiscard]] SnapshotFingerprint finish() const { return values_; }

 private:
  SnapshotFingerprint values_;
};

SnapshotFingerprint fingerprintImage(const Image& image) {
  FingerprintBuilder hash;
  hash.add(image.width());
  hash.add(image.height());
  for (const auto& pixel : image.pixels()) {
    hash.addByte(pixel.r);
    hash.addByte(pixel.g);
    hash.addByte(pixel.b);
    hash.addByte(pixel.a);
  }
  return hash.finish();
}

SnapshotFingerprint fingerprintSelection(const SelectionMask& selection) {
  FingerprintBuilder hash;
  hash.add(selection.width());
  hash.add(selection.height());
  for (const auto value : selection.values()) hash.addByte(value);
  return hash.finish();
}

SnapshotFingerprint fingerprintGeometry(const DetectionGeometry& geometry) {
  geometry.validate();
  FingerprintBuilder hash;
  hash.add(geometry.width());
  hash.add(geometry.height());
  for (const auto value : geometry.coloringGap.values()) hash.addByte(value);
  for (const auto value : geometry.lineBoundary.values()) hash.addByte(value);
  for (const auto value : geometry.guideBoundary.values()) hash.addByte(value);
  return hash.finish();
}

}  // namespace

CandidateContext captureCandidateContext(const Image& source, const Settings& settings,
                                         const SelectionMask* selection,
                                         const DetectionGeometry* geometry) {
  const auto normalized =
      geometry == nullptr ? normalizeCanonicalColoringGeometry(source)
                          : DetectionGeometry{};
  const auto& boundGeometry = geometry == nullptr ? normalized : *geometry;
  if (boundGeometry.width() != source.width() ||
      boundGeometry.height() != source.height())
    throw std::invalid_argument(
        "Candidate geometry dimensions do not match the source.");
  CandidateContext context;
  context.width = source.width();
  context.height = source.height();
  context.sourceFingerprint = fingerprintImage(source);
  context.geometryFingerprint = fingerprintGeometry(boundGeometry);
  context.hasSelection = selection != nullptr;
  if (selection != nullptr) context.selectionFingerprint = fingerprintSelection(*selection);
  context.scope = settings.scope;
  context.connectivity = settings.connectivity;
  context.confidencePreset = settings.confidencePreset;
  context.gapThreshold = settings.gapThreshold;
  context.alphaThreshold = settings.alphaThreshold;
  context.samplingRadius = settings.samplingRadius;
  context.ownerColorTolerance = settings.ownerColorTolerance;
  context.predictorOnnx = settings.predictorOnnx;
  return context;
}

void validateCandidateContext(const CandidateContext& context, const Image& source,
                              const Settings& settings,
                              const SelectionMask* selection,
                              const DetectionGeometry* geometry) {
  const auto normalized =
      geometry == nullptr ? normalizeCanonicalColoringGeometry(source)
                          : DetectionGeometry{};
  const auto& boundGeometry = geometry == nullptr ? normalized : *geometry;
  if (context.width != source.width() || context.height != source.height())
    throw std::invalid_argument("Candidate context dimensions do not match the source.");
  if (context.sourceFingerprint != fingerprintImage(source))
    throw std::invalid_argument("Candidate source snapshot is stale or does not match.");
  if (boundGeometry.width() != source.width() ||
      boundGeometry.height() != source.height())
    throw std::invalid_argument("Candidate geometry dimensions do not match the source.");
  if (context.geometryFingerprint != fingerprintGeometry(boundGeometry))
    throw std::invalid_argument("Candidate detection geometry is stale or does not match.");
  if (context.scope != settings.scope || context.connectivity != settings.connectivity ||
      context.confidencePreset != settings.confidencePreset ||
      context.gapThreshold != settings.gapThreshold ||
      context.alphaThreshold != settings.alphaThreshold ||
      context.samplingRadius != settings.samplingRadius ||
      context.ownerColorTolerance != settings.ownerColorTolerance ||
      context.predictorOnnx != settings.predictorOnnx) {
    throw std::invalid_argument("Candidate settings provenance does not match.");
  }
  if (context.hasSelection != (selection != nullptr))
    throw std::invalid_argument("Candidate selection provenance does not match.");
  if (selection != nullptr) {
    if (selection->width() != source.width() || selection->height() != source.height())
      throw std::invalid_argument("Selection dimensions do not match the source.");
    if (context.selectionFingerprint != fingerprintSelection(*selection))
      throw std::invalid_argument("Candidate selection snapshot is stale or does not match.");
  }
  if (settings.scope == Scope::SelectionOnly && selection == nullptr)
    throw std::invalid_argument("Selection-only candidates require a selection snapshot.");
}

}  // namespace gap_assist
