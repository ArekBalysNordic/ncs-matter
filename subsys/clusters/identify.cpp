/*
 * Copyright (c) 2026 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#include "clusters/identify.h"

#include <app/clusters/identify-server/identify-server.h>
#include <lib/support/CodeUtils.h>

namespace
{
using chip::EndpointId;
using chip::kInvalidEndpointId;
using chip::app::Clusters::Identify::EffectIdentifierEnum;
using chip::app::Clusters::Identify::EffectVariantEnum;

struct IdentifyCallbackContext {
	Nrf::Matter::IdentifyDelegateImplNrf * nrfDelegate = nullptr;
	chip::app::Clusters::IdentifyDelegate * customDelegate = nullptr;
};

constexpr size_t kMaxIdentifyInstances = CHIP_DEVICE_CONFIG_DYNAMIC_ENDPOINT_COUNT + 8;

struct IdentifyContextEntry {
	EndpointId endpoint = kInvalidEndpointId;
	IdentifyCallbackContext context{};
};

IdentifyContextEntry gIdentifyContexts[kMaxIdentifyInstances];

IdentifyCallbackContext * FindContext(EndpointId endpoint)
{
	for (IdentifyContextEntry & entry : gIdentifyContexts) {
		if (entry.endpoint == endpoint) {
			return &entry.context;
		}
	}
	return nullptr;
}

IdentifyCallbackContext * AllocateContext(EndpointId endpoint)
{
	for (IdentifyContextEntry & entry : gIdentifyContexts) {
		if (entry.endpoint == kInvalidEndpointId) {
			entry.endpoint = endpoint;
			return &entry.context;
		}
	}
	return nullptr;
}

void ReleaseContext(EndpointId endpoint)
{
	for (IdentifyContextEntry & entry : gIdentifyContexts) {
		if (entry.endpoint == endpoint) {
			entry.endpoint = kInvalidEndpointId;
			entry.context  = {};
			return;
		}
	}
}

void OnIdentifyStart(Identify * identify)
{
	EndpointId endpoint = identify->mCluster.Cluster().GetPaths()[0].mEndpointId;
	IdentifyCallbackContext * context = FindContext(endpoint);
	VerifyOrReturn(context != nullptr);

	if (context->customDelegate != nullptr) {
		context->customDelegate->OnIdentifyStart(identify->mCluster.Cluster());
	} else if (context->nrfDelegate != nullptr) {
		context->nrfDelegate->OnIdentifyStart(identify->mCluster.Cluster());
	}
}

void OnIdentifyStop(Identify * identify)
{
	EndpointId endpoint = identify->mCluster.Cluster().GetPaths()[0].mEndpointId;
	IdentifyCallbackContext * context = FindContext(endpoint);
	VerifyOrReturn(context != nullptr);

	if (context->customDelegate != nullptr) {
		context->customDelegate->OnIdentifyStop(identify->mCluster.Cluster());
	} else if (context->nrfDelegate != nullptr) {
		context->nrfDelegate->OnIdentifyStop(identify->mCluster.Cluster());
	}
}

void OnTriggerEffect(Identify * identify)
{
	EndpointId endpoint = identify->mCluster.Cluster().GetPaths()[0].mEndpointId;
	IdentifyCallbackContext * context = FindContext(endpoint);
	VerifyOrReturn(context != nullptr);

	if (context->customDelegate != nullptr) {
		context->customDelegate->OnTriggerEffect(identify->mCluster.Cluster());
	} else if (context->nrfDelegate != nullptr) {
		context->nrfDelegate->OnTriggerEffect(identify->mCluster.Cluster());
	}
}

} // namespace

namespace Nrf::Matter
{

IdentifyCluster::IdentifyCluster(chip::EndpointId endpoint, chip::app::Clusters::IdentifyDelegate &identifyDelegate,
				 chip::TimerDelegate &timerDelegate,
				 chip::app::Clusters::Identify::IdentifyTypeEnum identifyType)
	: mEndpointId(endpoint), mCustomDelegate(&identifyDelegate)
{
	IdentifyCallbackContext * context = AllocateContext(endpoint);
	VerifyOrDie(context != nullptr);
	context->customDelegate = &identifyDelegate;

	mIdentify = std::make_unique<Identify>(
		endpoint, OnIdentifyStart, OnIdentifyStop, identifyType, OnTriggerEffect,
		EffectIdentifierEnum::kBlink, EffectVariantEnum::kDefault, &timerDelegate);
}

IdentifyCluster::IdentifyCluster(chip::EndpointId endpoint, bool isTriggerEffectEnabled,
				 std::function<void()> customIdentifyStopCallback,
				 chip::app::Clusters::Identify::IdentifyTypeEnum identifyType)
	: mEndpointId(endpoint)
{
	mNrfDelegate.emplace(isTriggerEffectEnabled, customIdentifyStopCallback);

	IdentifyCallbackContext * context = AllocateContext(endpoint);
	VerifyOrDie(context != nullptr);
	context->nrfDelegate = &(*mNrfDelegate);

	Identify::onEffectIdentifierCb effectCb = isTriggerEffectEnabled ? OnTriggerEffect : nullptr;

	mIdentify = std::make_unique<Identify>(endpoint, OnIdentifyStart, OnIdentifyStop, identifyType, effectCb);
}

IdentifyCluster::~IdentifyCluster()
{
	mIdentify.reset();
	ReleaseContext(mEndpointId);
}

} // namespace Nrf::Matter
