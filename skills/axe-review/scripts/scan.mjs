#!/usr/bin/env node

import { readFile } from "node:fs/promises";
import { dirname, isAbsolute, resolve } from "node:path";
import process from "node:process";
import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright";

const DEFAULT_TIMEOUT_MS = 30_000;
const DEFAULT_VIEWPORT = { name: "desktop", width: 1440, height: 900 };
const VALID_FORMATS = new Set(["text", "json"]);
const IMPACT_ORDER = new Map([
  ["critical", 0],
  ["serious", 1],
  ["moderate", 2],
  ["minor", 3],
  [null, 4],
]);
const REQUIRED_RESOURCE_TYPES = new Set(["document", "script", "stylesheet"]);

function usage() {
  return `Usage:
  axe-review [options] <url-or-route>...
  axe-review --config <file>

Options:
  --base-url <url>          Base for relative routes
  --config <file>           JSON page and interaction manifest
  --storage-state <file>    Playwright authentication state
  --viewport <name=WxH>     Viewport, repeatable; defaults to desktop=1440x900
  --wait-for <selector>     Wait before scanning every CLI URL
  --include <selector>      Limit scans to a selector, repeatable
  --exclude <selector>      Exclude a selector, repeatable
  --tags <tag,tag>          Run only matching axe tags
  --timeout <milliseconds>  Navigation and action timeout
  --format <text|json>      Output format; defaults to text
  --help                    Show this help

Exit codes:
  0  No axe violations
  1  Violations found
  2  Configuration or scan failure`;
}

function takeValue(argv, index, option) {
  const value = argv[index + 1];
  if (!value || value.startsWith("--")) {
    throw new Error(`${option} requires a value`);
  }
  return value;
}

function parseViewport(value) {
  const match = /^(?:(?<name>[A-Za-z0-9_-]+)=)?(?<width>\d+)x(?<height>\d+)$/.exec(value);
  if (!match) {
    throw new Error(`Invalid viewport "${value}"; expected name=WIDTHxHEIGHT`);
  }
  const width = Number(match.groups.width);
  const height = Number(match.groups.height);
  if (width < 200 || height < 200) {
    throw new Error(`Viewport "${value}" must be at least 200x200`);
  }
  return {
    name: match.groups.name ?? `${width}x${height}`,
    width,
    height,
  };
}

function parseArgs(argv) {
  const options = {
    urls: [],
    viewports: [],
    include: [],
    exclude: [],
    format: "text",
  };

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    switch (argument) {
      case "--help":
      case "-h":
        options.help = true;
        break;
      case "--base-url":
        options.baseUrl = takeValue(argv, index, argument);
        index += 1;
        break;
      case "--config":
        options.configPath = takeValue(argv, index, argument);
        index += 1;
        break;
      case "--storage-state":
        options.storageState = takeValue(argv, index, argument);
        index += 1;
        break;
      case "--viewport":
        options.viewports.push(parseViewport(takeValue(argv, index, argument)));
        index += 1;
        break;
      case "--wait-for":
        options.waitFor = takeValue(argv, index, argument);
        index += 1;
        break;
      case "--include":
        options.include.push(takeValue(argv, index, argument));
        index += 1;
        break;
      case "--exclude":
        options.exclude.push(takeValue(argv, index, argument));
        index += 1;
        break;
      case "--tags":
        options.tags = takeValue(argv, index, argument)
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean);
        index += 1;
        break;
      case "--timeout":
        options.timeoutMs = Number(takeValue(argv, index, argument));
        index += 1;
        break;
      case "--format":
        options.format = takeValue(argv, index, argument);
        index += 1;
        break;
      default:
        if (argument.startsWith("--")) {
          throw new Error(`Unknown option: ${argument}`);
        }
        options.urls.push(argument);
    }
  }

  if (!VALID_FORMATS.has(options.format)) {
    throw new Error(`Invalid format "${options.format}"; expected text or json`);
  }
  if (options.timeoutMs !== undefined && (!Number.isInteger(options.timeoutMs) || options.timeoutMs <= 0)) {
    throw new Error("--timeout must be a positive integer");
  }
  return options;
}

function ensureStringArray(value, field) {
  if (value === undefined) return [];
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    throw new Error(`${field} must be an array of strings`);
  }
  return value;
}

function resolveFile(value, baseDirectory) {
  if (!value) return undefined;
  return isAbsolute(value) ? value : resolve(baseDirectory, value);
}

function normalizeViewport(viewport, field) {
  if (!viewport || typeof viewport !== "object") {
    throw new Error(`${field} must be an object`);
  }
  const width = Number(viewport.width);
  const height = Number(viewport.height);
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 200 || height < 200) {
    throw new Error(`${field} needs integer width and height of at least 200`);
  }
  return {
    name: typeof viewport.name === "string" ? viewport.name : `${width}x${height}`,
    width,
    height,
  };
}

function normalizePage(page, index) {
  if (!page || typeof page !== "object") {
    throw new Error(`pages[${index}] must be an object`);
  }
  const url = page.url ?? page.path;
  if (typeof url !== "string" || url.length === 0) {
    throw new Error(`pages[${index}] needs a non-empty url`);
  }
  if (page.actions !== undefined && !Array.isArray(page.actions)) {
    throw new Error(`pages[${index}].actions must be an array`);
  }
  return {
    name: typeof page.name === "string" ? page.name : url,
    url,
    waitFor: page.waitFor,
    include: ensureStringArray(page.include, `pages[${index}].include`),
    exclude: ensureStringArray(page.exclude, `pages[${index}].exclude`),
    actions: page.actions ?? [],
  };
}

async function loadConfiguration(cli) {
  let file = {};
  let configDirectory = process.cwd();
  if (cli.configPath) {
    const absoluteConfigPath = resolve(cli.configPath);
    configDirectory = dirname(absoluteConfigPath);
    try {
      file = JSON.parse(await readFile(absoluteConfigPath, "utf8"));
    } catch (error) {
      throw new Error(`Cannot read config ${absoluteConfigPath}: ${error.message}`);
    }
  }

  const filePages = file.pages === undefined ? [] : file.pages;
  if (!Array.isArray(filePages)) {
    throw new Error("pages must be an array");
  }
  const cliPages = cli.urls.map((url) => ({
    name: url,
    url,
    waitFor: cli.waitFor,
    include: cli.include,
    exclude: cli.exclude,
    actions: [],
  }));
  const pages = [...filePages.map(normalizePage), ...cliPages];
  if (pages.length === 0) {
    throw new Error("Provide at least one URL or a config with pages");
  }

  const fileViewports = file.viewports === undefined ? [] : file.viewports;
  if (!Array.isArray(fileViewports)) {
    throw new Error("viewports must be an array");
  }
  const viewports = cli.viewports.length > 0
    ? cli.viewports
    : fileViewports.length > 0
      ? fileViewports.map((viewport, index) => normalizeViewport(viewport, `viewports[${index}]`))
      : [DEFAULT_VIEWPORT];

  const tags = cli.tags ?? ensureStringArray(file.tags, "tags");
  const timeoutMs = cli.timeoutMs ?? file.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  if (!Number.isInteger(timeoutMs) || timeoutMs <= 0) {
    throw new Error("timeoutMs must be a positive integer");
  }

  return {
    baseUrl: cli.baseUrl ?? file.baseUrl,
    storageState: resolveFile(cli.storageState ?? file.storageState, cli.storageState ? process.cwd() : configDirectory),
    viewports,
    pages,
    tags,
    timeoutMs,
    format: cli.format,
  };
}

function resolveUrl(value, baseUrl) {
  let url;
  try {
    url = baseUrl ? new URL(value, baseUrl) : new URL(value);
  } catch {
    throw new Error(`Cannot resolve URL "${value}"${baseUrl ? ` against ${baseUrl}` : " without --base-url"}`);
  }
  if (!new Set(["http:", "https:"]).has(url.protocol)) {
    throw new Error(`Unsupported URL protocol: ${url.protocol}`);
  }
  return url.href;
}

async function performAction(page, action, timeoutMs, pageName, actionIndex) {
  if (!action || typeof action !== "object" || typeof action.type !== "string") {
    throw new Error(`${pageName} action ${actionIndex + 1} needs a type`);
  }
  const label = `${pageName} action ${actionIndex + 1} (${action.type})`;
  switch (action.type) {
    case "wait": {
      const milliseconds = Number(action.milliseconds);
      if (!Number.isInteger(milliseconds) || milliseconds <= 0 || milliseconds > timeoutMs) {
        throw new Error(`${label} needs integer milliseconds between 1 and ${timeoutMs}`);
      }
      await page.waitForTimeout(milliseconds);
      break;
    }
    case "click":
      await page.locator(action.selector).click({ timeout: timeoutMs });
      break;
    case "fill":
      await page.locator(action.selector).fill(String(action.value ?? ""), { timeout: timeoutMs });
      break;
    case "press":
      await page.locator(action.selector).press(action.key, { timeout: timeoutMs });
      break;
    case "check":
      await page.locator(action.selector).check({ timeout: timeoutMs });
      break;
    case "selectOption":
      await page.locator(action.selector).selectOption(action.value, { timeout: timeoutMs });
      break;
    case "waitFor":
      await page.locator(action.selector).waitFor({ state: "visible", timeout: timeoutMs });
      break;
    case "waitForURL":
      await page.waitForURL(action.url, { timeout: timeoutMs });
      break;
    default:
      throw new Error(`${label} has unsupported type`);
  }
}

function compactNode(node) {
  return {
    impact: node.impact,
    target: node.target,
    html: node.html,
    failureSummary: node.failureSummary,
  };
}

function compactResult(result) {
  return {
    id: result.id,
    impact: result.impact,
    description: result.description,
    help: result.help,
    helpUrl: result.helpUrl,
    tags: result.tags,
    nodes: result.nodes.map(compactNode),
  };
}

function isSameOrigin(url, requestedUrl) {
  try {
    return new URL(url).origin === new URL(requestedUrl).origin;
  } catch {
    return false;
  }
}

function uniqueFailures(failures) {
  return [...new Set(failures)];
}

async function scanPage(browser, config, viewport, pageDefinition) {
  let context;
  let page;
  let requestedUrl = pageDefinition.url;

  try {
    requestedUrl = resolveUrl(pageDefinition.url, config.baseUrl);
    const contextOptions = {
      viewport: { width: viewport.width, height: viewport.height },
    };
    if (config.storageState) contextOptions.storageState = config.storageState;
    context = await browser.newContext(contextOptions);
    page = await context.newPage();
    page.setDefaultTimeout(config.timeoutMs);
    const loadFailures = [];
    page.on("response", (response) => {
      const request = response.request();
      if (
        response.status() >= 400 &&
        REQUIRED_RESOURCE_TYPES.has(request.resourceType()) &&
        isSameOrigin(response.url(), requestedUrl)
      ) {
        loadFailures.push(`HTTP ${response.status()} ${request.resourceType()} ${response.url()}`);
      }
    });
    page.on("requestfailed", (request) => {
      if (
        REQUIRED_RESOURCE_TYPES.has(request.resourceType()) &&
        isSameOrigin(request.url(), requestedUrl)
      ) {
        loadFailures.push(`${request.resourceType()} ${request.url()}: ${request.failure()?.errorText ?? "request failed"}`);
      }
    });
    page.on("pageerror", (error) => {
      loadFailures.push(`page error: ${error.message}`);
    });
    const response = await page.goto(requestedUrl, {
      waitUntil: "load",
      timeout: config.timeoutMs,
    });
    if (response && response.status() >= 400) {
      throw new Error(`HTTP ${response.status()} at ${requestedUrl}`);
    }
    if (pageDefinition.waitFor) {
      await page.locator(pageDefinition.waitFor).waitFor({ state: "visible", timeout: config.timeoutMs });
    }
    for (const [index, action] of pageDefinition.actions.entries()) {
      await performAction(page, action, config.timeoutMs, pageDefinition.name, index);
    }

    const uniqueLoadFailures = uniqueFailures(loadFailures);
    if (uniqueLoadFailures.length > 0) {
      const visibleFailures = uniqueLoadFailures.slice(0, 5).join("; ");
      const remaining = uniqueLoadFailures.length - 5;
      throw new Error(
        `Page did not load its required assets: ${visibleFailures}${remaining > 0 ? `; ${remaining} more` : ""}`,
      );
    }

    const options = { resultTypes: ["violations"] };
    if (config.tags.length > 0) {
      options.runOnly = { type: "tag", values: config.tags };
    }
    let builder = new AxeBuilder({ page }).options(options);
    for (const selector of pageDefinition.include) builder = builder.include(selector);
    for (const selector of pageDefinition.exclude) builder = builder.exclude(selector);
    const result = await builder.analyze();

    return {
      name: pageDefinition.name,
      requestedUrl,
      finalUrl: page?.url() ?? requestedUrl,
      viewport,
      violations: result.violations.map(compactResult),
      incomplete: result.incomplete.map(compactResult),
    };
  } catch (error) {
    return {
      name: pageDefinition.name,
      requestedUrl,
      finalUrl: page?.url() ?? requestedUrl,
      viewport,
      violations: [],
      incomplete: [],
      error: error.message,
    };
  } finally {
    if (context) await context.close();
  }
}

function countNodes(results) {
  return results.reduce((sum, result) => sum + result.nodes.length, 0);
}

function summarize(scans) {
  return scans.reduce(
    (summary, scan) => {
      summary.scans += 1;
      if (scan.error) summary.errors += 1;
      summary.violationRules += scan.violations.length;
      summary.violationNodes += countNodes(scan.violations);
      summary.incompleteRules += scan.incomplete.length;
      summary.incompleteNodes += countNodes(scan.incomplete);
      return summary;
    },
    { scans: 0, errors: 0, violationRules: 0, violationNodes: 0, incompleteRules: 0, incompleteNodes: 0 },
  );
}

function sortResults(results) {
  return [...results].sort((left, right) => {
    const impact = (IMPACT_ORDER.get(left.impact) ?? 4) - (IMPACT_ORDER.get(right.impact) ?? 4);
    return impact || left.id.localeCompare(right.id);
  });
}

function printFinding(result, label) {
  const lines = [`  [${result.impact ?? "unknown"}] ${result.id}: ${result.help}`];
  const visibleNodes = result.nodes.slice(0, 5);
  for (const node of visibleNodes) {
    lines.push(`    ${label}: ${node.target.join(" -> ")}`);
    if (node.failureSummary) lines.push(`    ${node.failureSummary.replaceAll("\n", " ")}`);
  }
  if (result.nodes.length > visibleNodes.length) {
    lines.push(`    ... ${result.nodes.length - visibleNodes.length} more affected nodes; use --format json for all.`);
  }
  lines.push(`    ${result.helpUrl}`);
  return lines.join("\n");
}

function renderText(report) {
  const lines = [];
  for (const scan of report.scans) {
    lines.push(`\n${scan.name} [${scan.viewport.name}]`);
    lines.push(scan.finalUrl || scan.requestedUrl);
    if (scan.error) {
      lines.push(`  SCAN ERROR: ${scan.error}`);
      continue;
    }
    if (scan.violations.length === 0) lines.push("  Violations: none");
    for (const result of sortResults(scan.violations)) {
      lines.push(printFinding(result, "Target"));
    }
    if (scan.incomplete.length > 0) {
      lines.push("  Incomplete checks:");
      for (const result of sortResults(scan.incomplete)) {
        lines.push(printFinding(result, "Review"));
      }
    }
  }
  lines.push(
    `\nSummary: ${report.summary.scans} scans, ${report.summary.violationRules} violation rules, ` +
      `${report.summary.violationNodes} affected nodes, ${report.summary.incompleteRules} incomplete rules, ` +
      `${report.summary.errors} scan errors.`,
  );
  return lines.join("\n").trimStart();
}

async function main() {
  let cli;
  try {
    cli = parseArgs(process.argv.slice(2));
    if (cli.help) {
      console.log(usage());
      return 0;
    }
  } catch (error) {
    console.error(`axe-review: ${error.message}\n\n${usage()}`);
    return 2;
  }

  let config;
  try {
    config = await loadConfiguration(cli);
  } catch (error) {
    console.error(`axe-review: ${error.message}`);
    return 2;
  }

  let browser;
  try {
    browser = await chromium.launch({ headless: true });
  } catch (error) {
    console.error(`axe-review: cannot start Chromium: ${error.message}`);
    return 2;
  }

  const scans = [];
  try {
    for (const viewport of config.viewports) {
      for (const page of config.pages) {
        scans.push(await scanPage(browser, config, viewport, page));
      }
    }
  } finally {
    await browser.close();
  }

  const report = {
    generatedAt: new Date().toISOString(),
    tags: config.tags.length > 0 ? config.tags : ["all-enabled-rules"],
    scans,
    summary: summarize(scans),
  };
  console.log(config.format === "json" ? JSON.stringify(report, null, 2) : renderText(report));
  if (report.summary.errors > 0) return 2;
  return report.summary.violationNodes > 0 ? 1 : 0;
}

process.exitCode = await main();
