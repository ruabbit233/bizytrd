import { app } from "/scripts/app.js";

const UPDATE_WIDGET_NAME = "Update inputs";
const DYNAMIC_INPUT_STATE = Symbol("bizytrd.dynamicInputs");

function getWidget(node, name) {
  return node.widgets?.find((widget) => widget?.name === name) || null;
}

function clampCount(value, minimum, maximum) {
  const integer = Number.parseInt(value, 10);
  if (Number.isNaN(integer)) {
    return minimum;
  }
  return Math.min(Math.max(integer, minimum), maximum);
}

function getInputNames(node) {
  return (node.inputs || []).map((input) => input.name);
}

function ensureInputOrder(node) {
  if (!node[DYNAMIC_INPUT_STATE].inputOrder.length) {
    node[DYNAMIC_INPUT_STATE].inputOrder = getInputNames(node);
  }
}

function sortInputsByOriginalOrder(node) {
  if (!node.inputs?.length) {
    return;
  }
  const inputOrder = node[DYNAMIC_INPUT_STATE].inputOrder;
  if (!inputOrder.length) {
    return;
  }
  const orderMap = new Map(inputOrder.map((name, index) => [name, index]));
  node.inputs.sort((left, right) => {
    const leftIndex = orderMap.get(left.name);
    const rightIndex = orderMap.get(right.name);
    if (leftIndex == null && rightIndex == null) {
      return left.name.localeCompare(right.name);
    }
    if (leftIndex == null) {
      return 1;
    }
    if (rightIndex == null) {
      return -1;
    }
    return leftIndex - rightIndex;
  });
}

function parseInputSpec(spec) {
  if (Array.isArray(spec)) {
    const [typeSpec, extraInfo] = spec;
    const type = typeof typeSpec === "string" ? typeSpec : "*";
    return {
      type,
      extraInfo:
        extraInfo && typeof extraInfo === "object" ? { ...extraInfo } : undefined,
    };
  }
  if (typeof spec === "string") {
    return { type: spec, extraInfo: undefined };
  }
  return { type: "*", extraInfo: undefined };
}

function isMediaSpec(spec) {
  const { type } = parseInputSpec(spec);
  return type === "IMAGE" || type === "VIDEO" || type === "AUDIO";
}

function addInputFromSpec(node, inputName, spec) {
  const { type, extraInfo } = parseInputSpec(spec);
  node.addInput(inputName, type, extraInfo);
}

function removeInputByName(node, inputName) {
  const slot = node.inputs?.findIndex((input) => input.name === inputName) ?? -1;
  if (slot >= 0) {
    node.removeInput(slot);
  }
}


function syncDynamicInputs(node) {
  const state = node[DYNAMIC_INPUT_STATE];
  if (!state?.groups?.length) {
    return;
  }

  ensureInputOrder(node);

  for (const group of state.groups) {
    const inputCountWidget = getWidget(node, group.countWidgetName);
    const targetCount = clampCount(
      inputCountWidget?.value,
      1,
      group.maxInputCount,
    );

    if (inputCountWidget && inputCountWidget.value !== targetCount) {
      inputCountWidget.value = targetCount;
    }

    const keep = new Set([group.baseInput]);
    for (const extraInput of group.extraInputs) {
      if (extraInput.index <= targetCount) {
        keep.add(extraInput.name);
      }
    }

    for (const extraInput of [...group.extraInputs].sort((a, b) => b.index - a.index)) {
      if (!keep.has(extraInput.name)) {
        removeInputByName(node, extraInput.name);
      }
    }

    for (const extraInput of group.extraInputs) {
      if (!keep.has(extraInput.name)) {
        continue;
      }
      const exists = node.inputs?.some((input) => input.name === extraInput.name);
      if (!exists) {
        addInputFromSpec(node, extraInput.name, extraInput.spec);
      }
    }
  }

  sortInputsByOriginalOrder(node);
  if (typeof node.computeSize === "function") {
    node.size = node.computeSize();
  }
  node.setDirtyCanvas?.(true, true);
}

function ensureUpdateWidget(node) {
  if (getWidget(node, UPDATE_WIDGET_NAME)) {
    return;
  }
  node.addWidget(
    "button",
    UPDATE_WIDGET_NAME,
    null,
    () => syncDynamicInputs(node),
    { serialize: false },
  );
}



function scheduleSync(node) {
  window.setTimeout(() => {
    if (node?.inputs) {
      syncDynamicInputs(node);
    }
  }, 0);
}

function buildDynamicGroups(nodeData) {
  const required = nodeData?.input?.required || {};
  const optional = nodeData?.input?.optional || {};
  const allInputs = { ...required, ...optional };

  const groups = new Map();
  for (const [inputName, inputSpec] of Object.entries(optional)) {
    const match = inputName.match(/^(.*)_(\d+)$/);
    if (!match) {
      continue;
    }

    const [, prefix, indexText] = match;
    const index = Number.parseInt(indexText, 10);
    if (!Number.isInteger(index) || index < 2) {
      continue;
    }

    const candidateBases = [prefix, `${prefix}s`];
    const baseInput = candidateBases.find((name) =>
      Object.prototype.hasOwnProperty.call(allInputs, name),
    );
    if (!baseInput) {
      continue;
    }
    if (!isMediaSpec(inputSpec) || !isMediaSpec(allInputs[baseInput])) {
      continue;
    }

    if (!groups.has(baseInput)) {
      groups.set(baseInput, {
        baseInput,
        prefix,
        extraInputs: [],
      });
    }

    groups.get(baseInput).extraInputs.push({
      name: inputName,
      index,
      spec: inputSpec,
    });
  }

  return [...groups.values()]
    .map((group) => ({
      ...group,
      countWidgetName:
        [`${group.prefix}_inputcount`, `${group.baseInput}_inputcount`, "inputcount"].find(
          (widgetName) => Object.prototype.hasOwnProperty.call(allInputs, widgetName),
        ) || "inputcount",
      maxInputCount: 1 + group.extraInputs.length,
      extraInputs: group.extraInputs.sort((left, right) => left.index - right.index),
    }))
    .filter(
      (group) =>
        group.extraInputs.length > 0 &&
        Object.prototype.hasOwnProperty.call(allInputs, group.countWidgetName),
    );
}

function patchDynamicInputs(nodeType, nodeData) {
  const groups = buildDynamicGroups(nodeData);
  if (!groups.length) {
    return;
  }

  const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
  nodeType.prototype.onNodeCreated = function (...args) {
    this[DYNAMIC_INPUT_STATE] = {
      groups,
      inputOrder: [],
    };
    const result = originalOnNodeCreated?.apply(this, args);
    ensureUpdateWidget(this);
    scheduleSync(this);
    return result;
  };

  const originalOnConfigure = nodeType.prototype.onConfigure;
  nodeType.prototype.onConfigure = function (...args) {
    if (!this[DYNAMIC_INPUT_STATE]) {
      this[DYNAMIC_INPUT_STATE] = {
        groups,
        inputOrder: [],
      };
    }
    const result = originalOnConfigure?.apply(this, args);
    ensureUpdateWidget(this);
    syncDynamicInputs(this);
    return result;
  };
}

app.registerExtension({
  name: "bizytrd.dynamic-inputs",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (!String(nodeData?.name || "").startsWith("BizyTRD_")) {
      return;
    }
    patchDynamicInputs(nodeType, nodeData);
  },
});
