/*
 * Copyright (c) 2026 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#pragma once

#include <lib/core/CHIPError.h>

#if defined(CONFIG_DISABLE_THREAD_DIAGNOSTIC_RLOC16) || defined(CONFIG_DISABLE_THREAD_DIAGNOSTIC_EXTADDR)

#include <app-common/zap-generated/ids/Attributes.h>
#include <app/clusters/thread-network-diagnostics-server/DirectThreadNetworkDiagnosticsProvider.h>
#include <app/clusters/thread-network-diagnostics-server/ThreadNetworkDiagnosticsCluster.h>
#include <app/data-model-provider/MetadataTypes.h>
#include <app/server-cluster/ServerClusterInterfaceRegistry.h>
#include <app/util/attribute-storage.h>
#include <app/util/attribute-table.h>
#include <clusters/ThreadNetworkDiagnostics/AttributeIds.h>
#include <data-model-providers/codegen/CodegenDataModelProvider.h>
#include <lib/support/ReadOnlyBuffer.h>
#include <lib/support/logging/CHIPLogging.h>

namespace Nrf
{
namespace Matter
{

inline bool IsThreadNetworkDiagnosticAttributeDisabled(chip::AttributeId attributeId)
{
	using namespace chip::app::Clusters::ThreadNetworkDiagnostics::Attributes;

#if defined(CONFIG_DISABLE_THREAD_DIAGNOSTIC_EXTADDR)
	if (attributeId == ExtAddress::Id) {
		return true;
	}
#endif
#if defined(CONFIG_DISABLE_THREAD_DIAGNOSTIC_RLOC16)
	if (attributeId == Rloc16::Id) {
		return true;
	}
#endif
	return false;
}

namespace detail
{

using namespace chip;
using namespace chip::app;
using namespace chip::app::Clusters;
using namespace chip::app::Clusters::ThreadNetworkDiagnostics;

class CustomThreadNetworkDiagnosticsCluster : public ThreadNetworkDiagnosticsCluster {
public:
	using ThreadNetworkDiagnosticsCluster::ThreadNetworkDiagnosticsCluster;

	CHIP_ERROR Attributes(const ConcreteClusterPath &path,
			      ReadOnlyBufferBuilder<DataModel::AttributeEntry> &builder) override
	{
		ReadOnlyBufferBuilder<DataModel::AttributeEntry> baseAttributes;
		ReturnErrorOnFailure(ThreadNetworkDiagnosticsCluster::Attributes(path, baseAttributes));

		const auto allAttributes = baseAttributes.TakeBuffer();
		ReturnErrorOnFailure(builder.EnsureAppendCapacity(allAttributes.size()));

		for (const auto &entry : allAttributes) {
			if (IsThreadNetworkDiagnosticAttributeDisabled(entry.attributeId)) {
				continue;
			}
			ReturnErrorOnFailure(builder.Append(entry));
		}

		return CHIP_NO_ERROR;
	}
};

inline uint32_t LoadFeatureMap(EndpointId endpointId)
{
	using Traits = NumericAttributeTraits<uint32_t>;
	Traits::StorageType temp;
	uint8_t *readable = Traits::ToAttributeStoreRepresentation(temp);
	const Protocols::InteractionModel::Status status = emberAfReadAttribute(
		endpointId, ThreadNetworkDiagnostics::Id, Clusters::Globals::Attributes::FeatureMap::Id, readable, sizeof(temp));
	if (status != Protocols::InteractionModel::Status::Success) {
		return 0;
	}
	return Traits::StorageToWorking(temp);
}

constexpr EndpointId kThreadNetworkDiagnosticsEndpointId{};

inline LazyRegisteredServerCluster<CustomThreadNetworkDiagnosticsCluster> & GetClusterStorage()
{
	static LazyRegisteredServerCluster<CustomThreadNetworkDiagnosticsCluster> sCluster;
	return sCluster;
}

inline bool & IsClusterReplaced()
{
	static bool sInitialized;
	return sInitialized;
}

} /* namespace detail */

inline CHIP_ERROR InitThreadNetworkDiagnosticsCluster()
{
	using namespace detail;

	if (IsClusterReplaced()) {
		return CHIP_NO_ERROR;
	}

	auto &registry = CodegenDataModelProvider::Instance().Registry();
	ServerClusterInterface *existing =
		registry.Get({ kThreadNetworkDiagnosticsEndpointId, ThreadNetworkDiagnostics::Id });
	if (existing == nullptr) {
		return CHIP_NO_ERROR;
	}

	ReturnErrorOnFailure(registry.Unregister(existing, ClusterShutdownType::kClusterShutdown));

	const uint32_t featureMap = LoadFeatureMap(kThreadNetworkDiagnosticsEndpointId);
	const auto clusterType = featureMap == 0 ? ThreadNetworkDiagnosticsCluster::ClusterType::kMinimal
						 : ThreadNetworkDiagnosticsCluster::ClusterType::kFull;

	static DirectThreadNetworkDiagnosticsProvider sDirectProvider;

	auto &clusterStorage = GetClusterStorage();
	clusterStorage.Create(kThreadNetworkDiagnosticsEndpointId, clusterType, sDirectProvider);
	ReturnErrorOnFailure(registry.Register(clusterStorage.Registration()));

	IsClusterReplaced() = true;
	ChipLogProgress(AppServer, "Thread Network Diagnostics cluster customized (disabled attributes omitted from attribute list)");

	return CHIP_NO_ERROR;
}

} /* namespace Matter */
} /* namespace Nrf */

#else

namespace Nrf
{
namespace Matter
{

inline CHIP_ERROR InitThreadNetworkDiagnosticsCluster()
{
	return CHIP_NO_ERROR;
}

} /* namespace Matter */
} /* namespace Nrf */

#endif
