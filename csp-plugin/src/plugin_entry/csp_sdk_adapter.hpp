#pragma once

#include "plugin_entry/host_filter_context.hpp"

namespace gap_assist {

// This richer-host boundary is retained for a future SDK that can create layers
// and present the full review UI. The evaluated 2021 CELSYS filter SDK cannot
// satisfy that contract, so its private native adapter calls QuickFixPipeline
// directly. CELSYS SDK files must never be committed to this repository.
class CspSdkAdapter : public HostFilterContext {
 public:
  ~CspSdkAdapter() override = default;
};

}  // namespace gap_assist
