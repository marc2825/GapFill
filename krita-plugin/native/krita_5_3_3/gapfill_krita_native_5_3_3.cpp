// GapFill exact-patch transaction helper for the pinned Krita 5.3.3 host.
//
// This module is intentionally version pinned. Python supplies only validated
// immutable identity values and exact raw horizontal-run payloads.

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <windows.h>

#include <QCoreApplication>
#include <QPointer>
#include <QRect>
#include <QSharedPointer>
#include <QThread>
#include <QUuid>
#include <QVector>

#include <KisDocument.h>
#include <KisPart.h>
#include <KritaVersionWrapper.h>
#include <KoColorProfile.h>
#include <KoColorSpace.h>
#include <commands_new/kis_transaction_based_command.h>
#include <kis_image.h>
#include <kis_image_interfaces.h>
#include <kis_node.h>
#include <kis_paint_device.h>
#include <kis_paint_layer.h>
#include <kis_post_execution_undo_adapter.h>
#include <kis_stroke_strategy_undo_command_based.h>
#include <kis_transaction.h>

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <exception>
#include <limits>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

constexpr const char *kModuleName = "gapfill_krita_native_5_3_3";
constexpr const char *kHelperVersion = "1.0.0-krita-5.3.3-858d352";
constexpr const char *kExpectedKrita = "5.3.3 (git 858d352)";
constexpr const char *kExpectedQt = "5.15.7";
constexpr const char *kExpectedPythonPrefix = "3.13.5";
constexpr std::size_t kMaximumPixels = 1'000'000;
constexpr std::size_t kMaximumPayloadBytes = 16 * 1024 * 1024;

struct Run {
    int x = 0;
    int y = 0;
    int pixelCount = 0;
    std::vector<quint8> expectedBefore;
    std::vector<quint8> replacement;
};

struct Request {
    QUuid imageRootUuid;
    QUuid targetUuid;
    int width = 0;
    int height = 0;
    int originX = 0;
    int originY = 0;
    QString colorModel;
    QString colorDepth;
    QString profileName;
    std::vector<Run> runs;
    std::size_t pixelCount = 0;
    QRect dirtyRect;
};

struct CommandState {
    mutable std::mutex mutex;
    std::string status = "INTERNAL_EXCEPTION";
    std::string detail = "command did not complete";
    bool success = false;
    bool transactionStarted = false;
    bool transactionPublished = false;
    bool rollbackVerified = false;
    int sequenceBefore = -1;
    int sequenceAfter = -1;

    void finish(const char *newStatus, const std::string &newDetail, bool ok)
    {
        std::lock_guard<std::mutex> lock(mutex);
        status = newStatus;
        detail = newDetail;
        success = ok;
    }

    bool wasSuccessful() const
    {
        std::lock_guard<std::mutex> lock(mutex);
        return success;
    }
};

struct ResolvedTarget {
    QPointer<KisDocument> document;
    KisImageSP image;
    KisNodeSP node;
    KisPaintDeviceSP device;
};

class ImageBarrierGuard {
public:
    explicit ImageBarrierGuard(const KisImageSP &image)
        : m_image(image)
    {
        m_image->barrierLock(true);
    }

    ~ImageBarrierGuard()
    {
        if (m_image) {
            m_image->unlock();
        }
    }

    ImageBarrierGuard(const ImageBarrierGuard &) = delete;
    ImageBarrierGuard &operator=(const ImageBarrierGuard &) = delete;

private:
    KisImageSP m_image;
};

void countUuidMatches(const KisNodeSP &node, const QUuid &uuid, int &count, KisNodeSP &match)
{
    if (!node) {
        return;
    }
    if (node->uuid() == uuid) {
        ++count;
        match = node;
    }
    for (KisNodeSP child = node->firstChild(); child; child = child->nextSibling()) {
        countUuidMatches(child, uuid, count, match);
    }
}

bool validateHost(std::string &detail)
{
    if (sizeof(void *) != 8 || GetModuleHandleW(L"krita.exe") == nullptr) {
        detail = "requires the qualified Windows x64 Krita process";
        return false;
    }
    if (!QCoreApplication::instance() ||
        QThread::currentThread() != QCoreApplication::instance()->thread()) {
        detail = "apply_exact_patch must be called on Krita's GUI thread";
        return false;
    }
    if (KritaVersionWrapper::versionString(true) != QString::fromLatin1(kExpectedKrita)) {
        detail = "runtime Krita version/revision does not match 5.3.3 git 858d352";
        return false;
    }
    if (QString::fromLatin1(qVersion()) != QString::fromLatin1(kExpectedQt)) {
        detail = "runtime Qt version does not match 5.15.7";
        return false;
    }
    const char *pythonVersion = Py_GetVersion();
    if (!pythonVersion || std::strncmp(pythonVersion, kExpectedPythonPrefix, 6) != 0) {
        detail = "runtime Python does not match CPython 3.13.5";
        return false;
    }
    return true;
}

bool resolveTarget(const Request &request, ResolvedTarget &resolved, std::string &detail)
{
    int documentMatches = 0;
    QPointer<KisDocument> document;
    const QList<QPointer<KisDocument>> documents = KisPart::instance()->documents();
    for (const QPointer<KisDocument> &candidate : documents) {
        if (!candidate) {
            continue;
        }
        KisImageSP candidateImage = candidate->image();
        if (candidateImage && candidateImage->root() &&
            candidateImage->root()->uuid() == request.imageRootUuid) {
            ++documentMatches;
            document = candidate;
        }
    }
    if (documentMatches != 1 || !document) {
        detail = "image-root UUID did not resolve to exactly one open KisDocument";
        return false;
    }

    KisImageSP image = document->image();
    if (!image) {
        detail = "resolved document has no image";
        return false;
    }
    if (image->bounds() != QRect(request.originX, request.originY,
                                 request.width, request.height)) {
        detail = "document image bounds/origin mismatch";
        return false;
    }

    int nodeMatches = 0;
    KisNodeSP node;
    countUuidMatches(image->root(), request.targetUuid, nodeMatches, node);
    if (nodeMatches != 1 || !node) {
        detail = "target UUID did not resolve to exactly one node in the document image";
        return false;
    }
    if (node->image().data() != image.data()) {
        detail = "target node does not belong to the resolved image";
        return false;
    }

    KisPaintLayer *paintLayer = qobject_cast<KisPaintLayer *>(node.data());
    if (!paintLayer) {
        detail = "target node is not a KisPaintLayer";
        return false;
    }
    if (!node->isEditable(false) || node->userLocked() || paintLayer->alphaLocked()) {
        detail = "target paint layer is not editable";
        return false;
    }
    if (node->isAnimated()) {
        detail = "animated paint layers are excluded from the production helper";
        return false;
    }
    if (!node->visible() || node->opacity() != 255 ||
        node->compositeOpId() != QStringLiteral("normal") ||
        paintLayer->alphaChannelDisabled()) {
        detail = "target paint layer visibility/opacity/blending/inherit-alpha mismatch";
        return false;
    }

    KisPaintDeviceSP device = paintLayer->paintDevice();
    if (!device) {
        detail = "target paint layer has no paint device";
        return false;
    }
    if (device->x() != request.originX || device->y() != request.originY ||
        device->defaultBounds()->bounds() != image->bounds()) {
        detail = "target paint-device origin/bounds mismatch";
        return false;
    }

    const KoColorSpace *colorSpace = device->colorSpace();
    if (!colorSpace || colorSpace->colorModelId().id() != request.colorModel ||
        colorSpace->colorDepthId().id() != request.colorDepth ||
        colorSpace->pixelSize() != 4) {
        detail = "target color model/depth/pixel-size mismatch";
        return false;
    }
    const KoColorProfile *profile = colorSpace->profile();
    if (!profile || profile->name() != request.profileName) {
        detail = "target profile identity mismatch";
        return false;
    }

    resolved.document = document;
    resolved.image = image;
    resolved.node = node;
    resolved.device = device;
    return true;
}

bool validateCurrentBytes(const Request &request, const KisPaintDeviceSP &device,
                          std::vector<quint8> &scratch, std::string &detail)
{
    for (const Run &run : request.runs) {
        const std::size_t byteCount = run.expectedBefore.size();
        device->readBytes(scratch.data(), run.x, run.y, run.pixelCount, 1);
        if (std::memcmp(scratch.data(), run.expectedBefore.data(), byteCount) != 0) {
            detail = "expected-before bytes do not match the current paint device";
            return false;
        }
    }
    return true;
}

class ExactPatchCommand final : public KisTransactionBasedCommand {
public:
    ExactPatchCommand(Request request, ResolvedTarget resolved,
                      std::shared_ptr<CommandState> state)
        : KisTransactionBasedCommand(kundo2_noi18n(QStringLiteral("GapFill Apply")))
        , m_request(std::move(request))
        , m_document(resolved.document)
        , m_image(resolved.image)
        , m_node(resolved.node)
        , m_device(resolved.device)
        , m_state(std::move(state))
    {
        std::size_t maximumRunBytes = 0;
        for (const Run &run : m_request.runs) {
            maximumRunBytes = std::max(maximumRunBytes, run.expectedBefore.size());
        }
        m_scratch.resize(maximumRunBytes);
    }

protected:
    KUndo2Command *paint() override
    {
        std::unique_ptr<KisTransaction> transaction;
        try {
            std::string detail;
            if (!m_document || m_document->image().data() != m_image.data()) {
                m_state->finish("STALE_REJECTED", "document/image binding expired", false);
                return nullptr;
            }

            ResolvedTarget fresh;
            if (!resolveTarget(m_request, fresh, detail) ||
                fresh.document != m_document || fresh.image.data() != m_image.data() ||
                fresh.node.data() != m_node.data() || fresh.device.data() != m_device.data()) {
                m_state->finish("STALE_REJECTED", "target binding changed: " + detail, false);
                return nullptr;
            }

            m_state->sequenceBefore = m_device->sequenceNumber();
            if (!validateCurrentBytes(m_request, m_device, m_scratch, detail)) {
                m_state->finish("STALE_REJECTED", detail, false);
                return nullptr;
            }

            transaction = std::make_unique<KisTransaction>(
                kundo2_noi18n(QStringLiteral("GapFill Apply")), m_device);
            m_state->transactionStarted = true;

            for (const Run &run : m_request.runs) {
                m_device->writeBytes(run.replacement.data(), run.x, run.y,
                                     run.pixelCount, 1);
            }

            for (const Run &run : m_request.runs) {
                const std::size_t byteCount = run.replacement.size();
                m_device->readBytes(m_scratch.data(), run.x, run.y,
                                    run.pixelCount, 1);
                if (std::memcmp(m_scratch.data(), run.replacement.data(), byteCount) != 0) {
                    throw std::runtime_error("exact replacement readback mismatch");
                }
            }

            m_node->setDirty(m_request.dirtyRect);
            m_state->sequenceAfter = m_device->sequenceNumber();
            KUndo2Command *result = transaction->endAndTake();
            transaction.reset();
            m_state->transactionPublished = true;
            m_state->finish("SUCCESS", "exact patch applied and transaction captured", true);
            return result;
        } catch (const std::exception &exception) {
            return rollbackFailure(transaction, exception.what());
        } catch (...) {
            return rollbackFailure(transaction, "unknown native exception");
        }
    }

private:
    KUndo2Command *rollbackFailure(std::unique_ptr<KisTransaction> &transaction,
                                   const std::string &cause)
    {
        std::string detail = cause;
        if (transaction) {
            transaction->revert();
            transaction.reset();
            std::string verificationDetail;
            const bool restored = validateCurrentBytes(
                m_request, m_device, m_scratch, verificationDetail);
            m_state->rollbackVerified = restored;
            if (!restored) {
                detail += "; rollback verification failed: " + verificationDetail;
            }
            m_node->setDirty(m_request.dirtyRect);
        }
        m_state->finish("MUTATION_FAILURE", detail, false);
        return nullptr;
    }

    Request m_request;
    QPointer<KisDocument> m_document;
    KisImageSP m_image;
    KisNodeSP m_node;
    KisPaintDeviceSP m_device;
    std::shared_ptr<CommandState> m_state;
    std::vector<quint8> m_scratch;
};

class ExactPatchStrokeStrategy final : public KisStrokeStrategyUndoCommandBased {
public:
    ExactPatchStrokeStrategy(const QSharedPointer<ExactPatchCommand> &command,
                             const std::shared_ptr<CommandState> &state,
                             KisStrokeUndoFacade *undoFacade)
        : KisStrokeStrategyUndoCommandBased(
              kundo2_noi18n(QStringLiteral("GapFill Apply")), false, nullptr)
        , m_command(command)
        , m_state(state)
        , m_undoFacade(undoFacade)
    {
        setExclusive(true);
    }

    void finishStrokeCallback() override
    {
        KisStrokeStrategyUndoCommandBased::finishStrokeCallback();
        if (m_state->wasSuccessful()) {
            m_undoFacade->postExecutionUndoAdapter()->addCommand(m_command);
        }
    }

private:
    QSharedPointer<ExactPatchCommand> m_command;
    std::shared_ptr<CommandState> m_state;
    KisStrokeUndoFacade *m_undoFacade;
};

bool copyBytes(PyObject *object, std::vector<quint8> &destination, std::string &detail)
{
    char *data = nullptr;
    Py_ssize_t size = 0;
    if (PyBytes_AsStringAndSize(object, &data, &size) != 0) {
        detail = "run byte payloads must be bytes objects";
        return false;
    }
    if (size < 0) {
        detail = "negative byte payload length";
        return false;
    }
    destination.assign(reinterpret_cast<const quint8 *>(data),
                       reinterpret_cast<const quint8 *>(data) + size);
    return true;
}

bool parseRuns(PyObject *runsObject, Request &request, std::string &detail)
{
    PyObject *sequence = PySequence_Fast(runsObject, "runs must be a sequence");
    if (!sequence) {
        detail = "runs must be a sequence";
        return false;
    }

    const Py_ssize_t runCount = PySequence_Fast_GET_SIZE(sequence);
    if (runCount <= 0) {
        Py_DecRef(sequence);
        detail = "runs must not be empty";
        return false;
    }

    request.runs.reserve(static_cast<std::size_t>(runCount));
    std::size_t payloadBytes = 0;
    int previousY = std::numeric_limits<int>::min();
    std::int64_t previousEndX = std::numeric_limits<std::int64_t>::min();

    for (Py_ssize_t index = 0; index < runCount; ++index) {
        PyObject *item = PySequence_Fast_GET_ITEM(sequence, index);
        int x = 0;
        int y = 0;
        int pixelCount = 0;
        PyObject *expectedObject = nullptr;
        PyObject *replacementObject = nullptr;
        if (!PyArg_ParseTuple(item, "iiiOO:run", &x, &y, &pixelCount,
                              &expectedObject, &replacementObject)) {
            Py_DecRef(sequence);
            detail = "each run must be (x, y, pixel_count, expected_bytes, replacement_bytes)";
            return false;
        }

        if (pixelCount <= 0 || x < request.originX || y < request.originY) {
            Py_DecRef(sequence);
            detail = "run has invalid origin or pixel count";
            return false;
        }
        const std::int64_t endX = static_cast<std::int64_t>(x) + pixelCount;
        const std::int64_t imageEndX = static_cast<std::int64_t>(request.originX) + request.width;
        const std::int64_t imageEndY = static_cast<std::int64_t>(request.originY) + request.height;
        if (endX > imageEndX || static_cast<std::int64_t>(y) >= imageEndY) {
            Py_DecRef(sequence);
            detail = "run is outside the expected image bounds";
            return false;
        }
        if (y < previousY || (y == previousY && x < previousEndX)) {
            Py_DecRef(sequence);
            detail = "runs are not sorted or overlap";
            return false;
        }

        Run run;
        run.x = x;
        run.y = y;
        run.pixelCount = pixelCount;
        if (!copyBytes(expectedObject, run.expectedBefore, detail) ||
            !copyBytes(replacementObject, run.replacement, detail)) {
            Py_DecRef(sequence);
            return false;
        }
        const std::size_t requiredBytes = static_cast<std::size_t>(pixelCount) * 4;
        if (run.expectedBefore.size() != requiredBytes ||
            run.replacement.size() != requiredBytes) {
            Py_DecRef(sequence);
            detail = "run byte lengths must equal pixel_count * 4";
            return false;
        }

        request.pixelCount += static_cast<std::size_t>(pixelCount);
        payloadBytes += requiredBytes * 2;
        if (request.pixelCount > kMaximumPixels || payloadBytes > kMaximumPayloadBytes) {
            Py_DecRef(sequence);
            detail = "patch exceeds the production safety cap";
            return false;
        }

        const QRect runRect(x, y, pixelCount, 1);
        request.dirtyRect = request.dirtyRect.isNull()
            ? runRect
            : request.dirtyRect.united(runRect);
        request.runs.push_back(std::move(run));
        previousY = y;
        previousEndX = endX;
    }

    Py_DecRef(sequence);
    return true;
}

PyObject *buildResult(const std::shared_ptr<CommandState> &state,
                      const Request &request)
{
    std::lock_guard<std::mutex> lock(state->mutex);
    return Py_BuildValue(
        "{s:s,s:s,s:i,s:i,s:i,s:i,s:i,s:i,s:i,s:i,s:i,s:i,s:i,s:i}",
        "status", state->status.c_str(),
        "detail", state->detail.c_str(),
        "run_count", static_cast<int>(request.runs.size()),
        "pixel_count", static_cast<int>(request.pixelCount),
        "start_stroke_calls", 1,
        "end_stroke_calls", 1,
        "top_level_undo_commands", state->success ? 1 : 0,
        "transaction_commands", 1,
        "transaction_started", state->transactionStarted ? 1 : 0,
        "transaction_published", state->transactionPublished ? 1 : 0,
        "rollback_verified", state->rollbackVerified ? 1 : 0,
        "sequence_before", state->sequenceBefore,
        "sequence_after", state->sequenceAfter,
        "production_version_pinned", 1);
}

PyObject *applyExactPatch(PyObject *, PyObject *args, PyObject *kwargs)
{
    static const char *keywords[] = {
        "image_root_uuid", "target_uuid", "expected_width", "expected_height",
        "expected_origin_x", "expected_origin_y", "expected_color_model",
        "expected_color_depth", "expected_profile", "runs", nullptr};

    const char *imageRootUuid = nullptr;
    const char *targetUuid = nullptr;
    const char *colorModel = nullptr;
    const char *colorDepth = nullptr;
    const char *profileName = nullptr;
    int width = 0;
    int height = 0;
    int originX = 0;
    int originY = 0;
    PyObject *runsObject = nullptr;

    if (!PyArg_ParseTupleAndKeywords(
            args, kwargs, "ssiiiisssO:apply_exact_patch",
            const_cast<char **>(keywords), &imageRootUuid, &targetUuid,
            &width, &height, &originX, &originY, &colorModel, &colorDepth,
            &profileName, &runsObject)) {
        return nullptr;
    }

    try {
        Request request;
        request.imageRootUuid = QUuid(QString::fromUtf8(imageRootUuid));
        request.targetUuid = QUuid(QString::fromUtf8(targetUuid));
        request.width = width;
        request.height = height;
        request.originX = originX;
        request.originY = originY;
        request.colorModel = QString::fromLatin1(colorModel);
        request.colorDepth = QString::fromLatin1(colorDepth);
        request.profileName = QString::fromUtf8(profileName);

        auto state = std::make_shared<CommandState>();
        std::string detail;
        if (!validateHost(detail)) {
            state->finish("UNSUPPORTED_HOST", detail, false);
            return buildResult(state, request);
        }
        if (request.imageRootUuid.isNull() || request.targetUuid.isNull() ||
            request.width <= 0 || request.height <= 0 ||
            request.colorModel != QStringLiteral("RGBA") ||
            request.colorDepth != QStringLiteral("U8")) {
            state->finish("INVALID_REQUEST", "invalid UUID, dimensions, or RGBA/U8 contract", false);
            return buildResult(state, request);
        }
        if (!parseRuns(runsObject, request, detail)) {
            if (PyErr_Occurred()) {
                PyErr_Clear();
            }
            state->finish("INVALID_REQUEST", detail, false);
            return buildResult(state, request);
        }

        ResolvedTarget resolved;
        if (!resolveTarget(request, resolved, detail)) {
            state->finish("TARGET_REJECTED", detail, false);
            return buildResult(state, request);
        }
        {
            ImageBarrierGuard guard(resolved.image);
            std::size_t maximumRunBytes = 0;
            for (const Run &run : request.runs) {
                maximumRunBytes = std::max(maximumRunBytes, run.expectedBefore.size());
            }
            std::vector<quint8> scratch(maximumRunBytes);
            if (!resolveTarget(request, resolved, detail) ||
                !validateCurrentBytes(request, resolved.device, scratch, detail)) {
                state->finish("STALE_REJECTED", detail, false);
                return buildResult(state, request);
            }
        }

        QSharedPointer<ExactPatchCommand> command(
            new ExactPatchCommand(request, resolved, state));
        auto *strategy = new ExactPatchStrokeStrategy(command, state, resolved.image.data());
        const KisStrokeId strokeId = resolved.image->startStroke(strategy);
        resolved.image->addJob(
            strokeId,
            new KisStrokeStrategyUndoCommandBased::Data(
                command, false, KisStrokeJobData::BARRIER,
                KisStrokeJobData::EXCLUSIVE, false));
        resolved.image->endStroke(strokeId);
        resolved.image->waitForDone();

        return buildResult(state, request);
    } catch (const std::exception &exception) {
        PyErr_Format(PyExc_RuntimeError, "%s internal exception: %s", kModuleName,
                     exception.what());
        return nullptr;
    } catch (...) {
        PyErr_Format(PyExc_RuntimeError, "%s unknown internal exception", kModuleName);
        return nullptr;
    }
}

PyObject *abiInfo(PyObject *, PyObject *)
{
    return Py_BuildValue(
        "{s:s,s:s,s:s,s:s,s:s,s:s,s:s,s:s,s:s,s:s,s:i}",
        "helper_version", kHelperVersion,
        "compiler", "Clang/LLVM-MinGW 21.1.6",
        "architecture", "x86_64/AMD64",
        "python_abi", "cp313-win_amd64",
        "expected_krita", kExpectedKrita,
        "expected_qt", kExpectedQt,
        "crt", "UCRT",
        "cxx_standard_library", "libc++",
        "write_primitive", "KisPaintDevice::writeBytes",
        "transaction", "KisTransaction/endAndTake",
        "production_version_pinned", 1);
}

PyMethodDef kMethods[] = {
    {"abi_info", abiInfo, METH_NOARGS,
     "Return the compile-time ABI and architecture contract."},
    {"apply_exact_patch", reinterpret_cast<PyCFunction>(applyExactPatch),
     METH_VARARGS | METH_KEYWORDS,
     "Apply one exact, transaction-backed horizontal-run patch."},
    {nullptr, nullptr, 0, nullptr},
};

PyModuleDef kModule = {
    PyModuleDef_HEAD_INIT,
    kModuleName,
    "Version-pinned GapFill exact transaction helper for Krita 5.3.3.",
    -1,
    kMethods,
};

} // namespace

PyMODINIT_FUNC PyInit_gapfill_krita_native_5_3_3()
{
    std::string detail;
    if (!validateHost(detail)) {
        PyErr_Format(PyExc_ImportError, "%s", detail.c_str());
        return nullptr;
    }
    return PyModule_Create(&kModule);
}
