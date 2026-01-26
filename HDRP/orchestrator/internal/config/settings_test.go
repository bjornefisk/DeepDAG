package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func writeConfig(t *testing.T, dir, name, content string) string {
	t.Helper()
	path := filepath.Join(dir, name)
	if err := os.WriteFile(path, []byte(content), 0644); err != nil {
		t.Fatalf("write config: %v", err)
	}
	return path
}

func TestLoad_DefaultEnvironmentOverlay(t *testing.T) {
	dir := t.TempDir()
	base := `
services:
  principal:
    address: "base-principal"
  researcher:
    address: "base-researcher"
  critic:
    address: "base-critic"
  synthesizer:
    address: "base-synthesizer"
concurrency:
  max_workers: 4
`
	overlay := `
services:
  principal:
    address: "overlay-principal"
`
	basePath := writeConfig(t, dir, "config.yaml", base)
	_ = writeConfig(t, dir, "config.development.yaml", overlay)

	cfg, err := Load(basePath)
	if err != nil {
		t.Fatalf("Load failed: %v", err)
	}

	if cfg.Services.Principal.Address != "overlay-principal" {
		t.Fatalf("expected overlay principal address, got %q", cfg.Services.Principal.Address)
	}
}

func TestLoad_EnvOverrides(t *testing.T) {
	dir := t.TempDir()
	base := `
services:
  principal:
    address: "base-principal"
  researcher:
    address: "base-researcher"
  critic:
    address: "base-critic"
  synthesizer:
    address: "base-synthesizer"
concurrency:
  max_workers: 2
`
	basePath := writeConfig(t, dir, "config.yaml", base)

	t.Setenv("HDRP_SERVICES_PRINCIPAL_ADDRESS", "env-principal")

	cfg, err := Load(basePath)
	if err != nil {
		t.Fatalf("Load failed: %v", err)
	}

	if cfg.Services.Principal.Address != "env-principal" {
		t.Fatalf("expected env principal address, got %q", cfg.Services.Principal.Address)
	}
}

func TestLoad_ValidationFailure(t *testing.T) {
	dir := t.TempDir()
	badConfig := `
services:
  principal:
    address: ""
  researcher:
    address: "base-researcher"
  critic:
    address: "base-critic"
  synthesizer:
    address: "base-synthesizer"
concurrency:
  max_workers: 1
`
	basePath := writeConfig(t, dir, "config.yaml", badConfig)

	_, err := Load(basePath)
	if err == nil {
		t.Fatal("expected validation error")
	}
	if !strings.Contains(err.Error(), "services.principal.address") {
		t.Fatalf("unexpected error: %v", err)
	}
}
