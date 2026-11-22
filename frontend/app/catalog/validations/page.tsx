"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useAuth } from "@/components/auth-provider";
import { apiRequest } from "@/lib/auth-client";
import { BrandedLoading } from "@/components/branded-loading";

type ValidationProfile = {
  id: string;
  name: string;
  dataset_type: string;
  description: string | null;
  is_active: boolean;
};
type ValidationRule = {
  id: string;
  profile_id: string;
  code: string;
  name: string;
  field_name: string;
  rule_type: string;
  config: Record<string, unknown>;
  severity: "critical" | "warning" | "info";
  enabled: boolean;
};
type EvaluationResult = {
  filename: string;
  total_records: number;
  rules: { code: string; name: string; status: string; records_evaluated: number; issue_records: number | null }[];
  errors: { source_location: string; field: string; error_code: string; message: string; severity: string }[];
};

const RULE_TYPES = [
  "required", "unique", "numeric_min", "numeric_max",
  "allowed_values", "min_length", "max_length",
];

export default function ValidationProfilesPage() {
  const { user, loading: authLoading } = useAuth();
  const [profiles, setProfiles] = useState<ValidationProfile[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [rules, setRules] = useState<ValidationRule[]>([]);
  const [profileName, setProfileName] = useState("");
  const [datasetType, setDatasetType] = useState("product catalog");
  const [ruleCode, setRuleCode] = useState("");
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null);
  const [ruleName, setRuleName] = useState("");
  const [fieldName, setFieldName] = useState("");
  const [ruleType, setRuleType] = useState("required");
  const [ruleConfig, setRuleConfig] = useState("{}");
  const [severity, setSeverity] = useState<"critical" | "warning" | "info">("warning");
  const [file, setFile] = useState<File | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const loadProfiles = useCallback(async () => {
    const data = await apiRequest<ValidationProfile[]>("/api/v1/validation/profiles");
    setProfiles(data);
    setSelectedId((current) => current || data[0]?.id || "");
  }, []);

  const loadRules = useCallback(async (profileId: string) => {
    const data = await apiRequest<ValidationRule[]>(`/api/v1/validation/profiles/${profileId}/rules`);
    setRules(data);
  }, []);

  useEffect(() => {
    if (!user) return;
    let active = true;
    apiRequest<ValidationProfile[]>("/api/v1/validation/profiles")
      .then((data) => {
        if (!active) return;
        setProfiles(data);
        setSelectedId((current) => current || data[0]?.id || "");
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Could not load validation profiles.");
      });
    return () => { active = false; };
  }, [user]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    apiRequest<ValidationRule[]>(`/api/v1/validation/profiles/${selectedId}/rules`)
      .then((data) => { if (active) setRules(data); })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Could not load validation rules.");
      });
    return () => { active = false; };
  }, [selectedId]);

  async function createProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true); setError("");
    try {
      const profile = await apiRequest<ValidationProfile>("/api/v1/validation/profiles", {
        method: "POST",
        body: JSON.stringify({ name: profileName, dataset_type: datasetType }),
        headers: { "Content-Type": "application/json" },
      });
      setProfileName("");
      await loadProfiles();
      setSelectedId(profile.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create validation profile.");
    } finally { setLoading(false); }
  }

  async function createRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedId) return;
    setLoading(true); setError("");
    try {
      let config: Record<string, unknown>;
      try { config = JSON.parse(ruleConfig) as Record<string, unknown>; }
      catch { throw new Error("Rule configuration must be valid JSON."); }
      if (editingRuleId) {
        await apiRequest<ValidationRule>(`/api/v1/validation/profiles/${selectedId}/rules/${editingRuleId}`, {
          method: "PATCH",
          body: JSON.stringify({ name: ruleName, field_name: fieldName, config, severity }),
          headers: { "Content-Type": "application/json" },
        });
      } else {
        await apiRequest<ValidationRule>(`/api/v1/validation/profiles/${selectedId}/rules`, {
          method: "POST",
          body: JSON.stringify({
            code: ruleCode.trim().toUpperCase(), name: ruleName, field_name: fieldName,
            rule_type: ruleType, config, severity, enabled: true,
          }),
          headers: { "Content-Type": "application/json" },
        });
      }
      setEditingRuleId(null); setRuleCode(""); setRuleName(""); setFieldName(""); setRuleConfig("{}");
      setEvaluation(null);
      await loadRules(selectedId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create validation rule.");
    } finally { setLoading(false); }
  }

  function beginEditRule(rule: ValidationRule) {
    setEditingRuleId(rule.id);
    setRuleCode(rule.code);
    setRuleName(rule.name);
    setFieldName(rule.field_name);
    setRuleType(rule.rule_type);
    setRuleConfig(JSON.stringify(rule.config ?? {}, null, 2));
    setSeverity(rule.severity);
    setError("");
    setEvaluation(null);
  }

  async function toggleRule(rule: ValidationRule) {
    setError("");
    try {
      await apiRequest<ValidationRule>(`/api/v1/validation/profiles/${selectedId}/rules/${rule.id}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: !rule.enabled }),
        headers: { "Content-Type": "application/json" },
      });
      setEvaluation(null);
      await loadRules(selectedId);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not update rule."); }
  }

  async function deleteRule(rule: ValidationRule) {
    setError("");
    try {
      await apiRequest<void>(`/api/v1/validation/profiles/${selectedId}/rules/${rule.id}`, { method: "DELETE" });
      setEvaluation(null);
      await loadRules(selectedId);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not delete rule."); }
  }

  async function toggleProfile(profile: ValidationProfile) {
    setError("");
    try {
      await apiRequest<ValidationProfile>(`/api/v1/validation/profiles/${profile.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !profile.is_active }),
        headers: { "Content-Type": "application/json" },
      });
      setEvaluation(null);
      await loadProfiles();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not update profile."); }
  }

  async function runEvaluation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedId || !file) return;
    setLoading(true); setError(""); setEvaluation(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const data = await apiRequest<EvaluationResult>(`/api/v1/validation/profiles/${selectedId}/evaluate`, {
        method: "POST", body,
      });
      setEvaluation(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not evaluate custom rules.");
    } finally { setLoading(false); }
  }

  if (authLoading) return <main id="main" className="page"><div className="container"><BrandedLoading label="Checking your account" detail="Loading validation workspace." /></div></main>;
  if (!user) return <main id="main" className="page"><div className="container"><section className="panel"><h1>Sign in required</h1><p>Sign in to manage organization validation profiles.</p><a className="button" href="/sign-in">Sign in</a></section></div></main>;

  const selectedProfile = profiles.find((profile) => profile.id === selectedId) ?? null;

  return (
    <main id="main" className="page">
      <div className="container">
        <div className="import-heading">
          <div className="eyebrow">DATA QUALITY CONFIGURATION</div>
          <h1>Validation profiles and custom rules</h1>
          <p>Create reusable organization-specific rules. Rules are declarative and restricted to supported operations; customer input is never executed as code.</p>
        </div>

        {error && <div className="import-error" role="alert">{error}</div>}

        <section className="panel import-panel">
          <h2>Create a validation profile</h2>
          <form onSubmit={createProfile} className="form-grid">
            <label>Profile name<input value={profileName} onChange={(event) => setProfileName(event.target.value)} required maxLength={120} /></label>
            <label>Dataset type<input value={datasetType} onChange={(event) => setDatasetType(event.target.value)} required maxLength={60} /></label>
            <button className="button" type="submit" disabled={loading}>Create profile</button>
          </form>
        </section>

        <section className="panel import-panel">
          <h2>Choose a profile</h2>
          {profiles.length === 0 ? <p>No custom profiles yet.</p> : <>
            <label>Validation profile<select value={selectedId} onChange={(event) => { setSelectedId(event.target.value); setEvaluation(null); }}>
              {profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name} · {profile.dataset_type}</option>)}
            </select></label>
            {selectedProfile && <p className="import-description">Status: {selectedProfile.is_active ? "Active" : "Disabled"} <button className="button button-secondary" type="button" onClick={() => toggleProfile(selectedProfile)}>{selectedProfile.is_active ? "Disable profile" : "Enable profile"}</button></p>}
          </>}
        </section>

        {selectedProfile?.is_active && <section className="panel import-panel">
          <h2>{editingRuleId ? "Edit custom rule" : "Add a custom rule"}</h2>
          <p className="import-description">Use a source column name exactly as it appears in the uploaded file. Examples: required, unique, numeric minimum/maximum, allowed values, and minimum/maximum text length.</p>
          <form onSubmit={createRule} className="form-grid">
            <label>Rule code<input value={ruleCode} onChange={(event) => setRuleCode(event.target.value)} required maxLength={80} placeholder="SKU_REQUIRED" disabled={Boolean(editingRuleId)} /></label>
            <label>Rule name<input value={ruleName} onChange={(event) => setRuleName(event.target.value)} required maxLength={120} /></label>
            <label>Source field<input value={fieldName} onChange={(event) => setFieldName(event.target.value)} required maxLength={120} placeholder="sku" /></label>
            <label>Rule type<select value={ruleType} onChange={(event) => setRuleType(event.target.value)} disabled={Boolean(editingRuleId)}>
              {RULE_TYPES.map((type) => <option key={type} value={type}>{type.replaceAll("_", " ")}</option>)}
            </select></label>
            <label>Rule configuration (JSON)<textarea value={ruleConfig} onChange={(event) => setRuleConfig(event.target.value)} rows={3} /></label>
            <label>Severity<select value={severity} onChange={(event) => setSeverity(event.target.value as typeof severity)}>
              <option value="critical">Critical</option><option value="warning">Warning</option><option value="info">Informational</option>
            </select></label>
            <button className="button" type="submit" disabled={loading}>{editingRuleId ? "Save rule changes" : "Add rule"}</button>
            {editingRuleId && <button className="button button-secondary" type="button" onClick={() => { setEditingRuleId(null); setRuleCode(""); setRuleName(""); setFieldName(""); setRuleConfig("{}"); }}>Cancel edit</button>}
          </form>
          <p className="column-hint">Configuration examples: <code>{'{"value": 0}'}</code> for numeric minimum, <code>{'{"values": ["active", "inactive"]}'}</code> for allowed values, and <code>{'{"value": 10}'}</code> for length. Required and unique use an empty object.</p>
        </section>}

        {selectedProfile && <section className="panel import-panel">
          <h2>Rules in {selectedProfile.name}</h2>
          {rules.length === 0 ? <p>No custom rules have been added to this profile.</p> : <div className="table-scroll"><table className="preview-table"><thead><tr><th>Rule</th><th>Field</th><th>Type</th><th>Severity</th><th>Status</th><th>Actions</th></tr></thead><tbody>
            {rules.map((rule) => <tr key={rule.id}><td>{rule.name}<small>{rule.code}</small></td><td>{rule.field_name}</td><td>{rule.rule_type}</td><td>{rule.severity}</td><td>{rule.enabled ? "Enabled" : "Disabled — not evaluated"}</td><td><button className="button button-secondary" type="button" onClick={() => beginEditRule(rule)}>Edit</button> <button className="button button-secondary" type="button" onClick={() => toggleRule(rule)}>{rule.enabled ? "Disable" : "Enable"}</button> <button className="button button-secondary" type="button" onClick={() => deleteRule(rule)}>Delete</button></td></tr>)}
          </tbody></table></div>}
        </section>}

        {selectedProfile?.is_active && rules.some((rule) => rule.enabled) && <section className="panel import-panel">
          <h2>Evaluate custom rules</h2>
          <p className="import-description">The selected file stays in this browser tab while you edit rules, so you do not need to choose it again. Each evaluation request sends the file to the backend again; CompatFlow does not retain the uploaded file after the request.</p>
          <form onSubmit={runEvaluation} className="form-grid">
            <label>Dataset file<input type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} required /></label>
            <button className="button" type="submit" disabled={!file || loading}>{evaluation ? "Re-run selected file" : "Run custom validation"}</button>
          </form>
          {evaluation && <>
            <p>{evaluation.filename} · {evaluation.total_records.toLocaleString()} records</p>
            <div className="table-scroll"><table className="preview-table"><thead><tr><th>Rule</th><th>Status</th><th>Records evaluated</th><th>Missing skipped</th><th>Issues</th></tr></thead><tbody>{evaluation.rules.map((rule) => <tr key={rule.code}><td>{rule.name}</td><td>{rule.status === "not_evaluated" ? "Not evaluated" : "Evaluated"}</td><td>{rule.records_evaluated.toLocaleString()}</td><td>{(rule.records_skipped_missing ?? 0).toLocaleString()}</td><td>{rule.issue_records === null ? "—" : rule.issue_records.toLocaleString()}</td></tr>)}</tbody></table></div>
            {evaluation.errors.length > 0 && <div className="table-scroll"><table className="preview-table"><thead><tr><th>Source location</th><th>Field</th><th>Severity</th><th>Issue</th></tr></thead><tbody>{evaluation.errors.map((issue, index) => <tr key={index}><td>{issue.source_location}</td><td>{issue.field}</td><td>{issue.severity}</td><td>{issue.message}</td></tr>)}</tbody></table></div>}
          </>}
        </section>}
      </div>
    </main>
  );
}
