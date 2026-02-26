#!/usr/bin/env python3
import unittest
import subprocess
import time
import json
import base64
import requests
import atexit
from contextlib import contextmanager

"""
End-to-end integration tests for the BBOT Server Helm chart running on minikube.

Run it like so:

# all tests
uv run python test_helm_deployment.py

# specific test
uv run python -m unittest test_helm_deployment.TestHelmDeployment.test_swagger_ui

To bring up the test environment manually, run:

minikube start
docker build -t blacklanternsecurity/bbot-server:test .
minikube image load blacklanternsecurity/bbot-server:test
helm dependency update helm/
helm install bbot helm/ --set image.tag=test --set image.pullPolicy=Never
"""


class TestHelmDeployment(unittest.TestCase):
    release_name = "bbot"
    ctx = ["--context", "minikube"]
    kube_ctx = ["--kube-context", "minikube"]
    _cleanup_registered = False

    @classmethod
    def run_command(cls, command, timeout=120, **kwargs):
        print(f"Running: {' '.join(command)}")
        if "check" not in kwargs:
            kwargs["check"] = True
        return subprocess.run(command, text=True, timeout=timeout, **kwargs)

    @classmethod
    def kubectl(cls, *command, **kwargs):
        return cls.run_command(["kubectl", *cls.ctx, *command], **kwargs)

    @classmethod
    def helm(cls, *command, **kwargs):
        return cls.run_command(["helm", *cls.kube_ctx, *command], **kwargs)

    @classmethod
    @contextmanager
    def port_forward(cls, service, local_port, remote_port):
        """Context manager for kubectl port-forward"""
        process = subprocess.Popen(
            ["kubectl", *cls.ctx, "port-forward", f"svc/{service}", f"{local_port}:{remote_port}"],
        )
        try:
            # Wait for port-forward to establish
            time.sleep(3)
            yield f"http://localhost:{local_port}"
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    @classmethod
    def cleanup_resources(cls):
        """Clean up Helm charts and PVCs - ALWAYS runs"""
        print("\nCLEANING UP RESOURCES...")
        print("-" * 40)

        # Uninstall Helm chart
        print("Uninstalling Helm chart...")
        cls.helm("uninstall", cls.release_name, check=False)

        # Delete any existing PVCs to ensure clean state
        print("Deleting any existing PVCs...")
        cls.kubectl("delete", "pvc", "--all", check=False)

        # Delete leftover secrets with keep policy
        for suffix in ("mongodb", "redis", "api-key"):
            cls.kubectl("delete", "secret", f"{cls.release_name}-{suffix}", check=False)

        print("Cleanup completed")

    @classmethod
    def register_cleanup(cls):
        """Register cleanup to run on exit"""
        if not cls._cleanup_registered:
            atexit.register(cls.cleanup_resources)
            cls._cleanup_registered = True

    @classmethod
    def dump_cluster_debug_info(cls):
        """Print pods, logs, services, and events for debugging"""
        print("\n" + "=" * 80)
        print("ALL PODS STATUS:")
        print("-" * 40)
        try:
            result = cls.kubectl("get", "pods", "-o", "wide", capture_output=True, check=False)
            print(result.stdout)
        except Exception as e:
            print(f"Failed to get pods: {e}")

        print("\nPOD LOGS:")
        print("-" * 40)
        try:
            result = cls.kubectl(
                "get",
                "pods",
                "-o",
                "jsonpath='{.items[*].metadata.name}'",
                capture_output=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                pod_names = result.stdout.strip().strip("'").split()
                for pod_name in pod_names:
                    print(f"\nLogs for pod: {pod_name}")
                    print("-" * 30)
                    try:
                        log_result = cls.kubectl(
                            "logs",
                            pod_name,
                            "--all-containers",
                            "--tail=200",
                            capture_output=True,
                            check=False,
                        )
                        if log_result.returncode == 0:
                            print(log_result.stdout)
                        else:
                            print(f"Failed to get logs: {log_result.stderr}")
                    except Exception as e:
                        print(f"Error getting logs for {pod_name}: {e}")
            else:
                print("Failed to list pods or no pods found")
        except Exception as e:
            print(f"Failed to get pod names: {e}")

        print("\nSERVICES STATUS:")
        print("-" * 40)
        try:
            result = cls.kubectl("get", "services", "-o", "wide", capture_output=True, check=False)
            print(result.stdout)
        except Exception as e:
            print(f"Failed to get services: {e}")

        print("\nRECENT EVENTS:")
        print("-" * 40)
        try:
            result = cls.kubectl(
                "get",
                "events",
                "--sort-by=.metadata.creationTimestamp",
                capture_output=True,
                check=False,
            )
            print(result.stdout)
        except Exception as e:
            print(f"Failed to get events: {e}")
        print("\n" + "=" * 80)

    @classmethod
    def setUpClass(cls):
        """Build image, deploy to minikube, wait for readiness"""

        # Ensure minikube is running
        print("Checking if minikube is running...")
        result = subprocess.run(
            ["minikube", "status"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or "Running" not in result.stdout:
            print("Starting minikube...")
            subprocess.run(["minikube", "start"], check=True)
            print("Minikube started")
        else:
            print("Minikube is already running")

        # Register cleanup to ALWAYS run, even on test failure
        cls.register_cleanup()

        # Clean up any previous deployments
        cls.cleanup_resources()

        # Build image locally and load into minikube
        print("Building Docker image...")
        cls.run_command(
            [
                "docker",
                "build",
                "-t",
                "blacklanternsecurity/bbot-server:test",
                ".",
            ],
            timeout=300,
        )
        print("Loading image into minikube...")
        cls.run_command(
            [
                "minikube",
                "image",
                "load",
                "blacklanternsecurity/bbot-server:test",
            ],
            timeout=120,
        )
        print("Image loaded successfully")

        # Update Helm dependencies
        print("Updating Helm dependencies...")
        cls.helm("dependency", "update", "helm/", timeout=60)

        # Deploy the helm chart
        print("Deploying helm chart...")
        cls.helm(
            "install",
            cls.release_name,
            "helm/",
            "--set",
            "image.tag=test",
            "--set",
            "image.pullPolicy=Never",
            timeout=60,
        )

        # Wait for server pod to be ready
        print("Waiting for server pod to be ready...")
        result = cls.kubectl(
            "wait",
            "--for=condition=ready",
            "pod",
            "-l",
            "app=bbot-server",
            "--timeout=90s",
            check=False,
            capture_output=True,
            timeout=100,
        )
        if result.returncode == 0:
            print("Server pod is ready")
            return

        print("\n" + "=" * 80)
        print("TIMEOUT: Server pod failed to become ready")
        print("=" * 80)
        cls.dump_cluster_debug_info()
        raise RuntimeError("Timed out waiting for server pod to be ready")

    def test_swagger_ui(self):
        """Test that the swagger-ui loads properly at /v1/docs"""
        with self.port_forward(f"{self.release_name}-server", 8807, 8807) as base_url:
            response = requests.get(f"{base_url}/v1/docs", timeout=10)
            print(f"GET /v1/docs status: {response.status_code}")
            print(f"Content length: {len(response.text)}")

            self.assertEqual(response.status_code, 200, "Swagger UI should return 200")
            self.assertIn("swagger-ui", response.text.lower(), "Response should contain swagger-ui")

    def test_ingest_and_query_assets(self):
        """Test ingesting events from evilcorp.json.gz and querying assets via bbctl"""
        # Get the server pod name
        result = self.kubectl(
            "get",
            "pods",
            "-l",
            "app=bbot-server",
            "-o",
            "jsonpath={.items[0].metadata.name}",
            capture_output=True,
        )
        pod_name = result.stdout.strip()
        self.assertTrue(pod_name, "Should find a server pod")
        print(f"Server pod: {pod_name}")

        # Get the API key from the kubernetes secret
        result = self.kubectl(
            "get",
            "secret",
            f"{self.release_name}-api-key",
            "-o",
            "jsonpath={.data.api-key}",
            capture_output=True,
        )
        api_key = base64.b64decode(result.stdout).decode()
        self.assertTrue(api_key, "Should retrieve API key from secret")

        # Write a bbctl config file inside the pod
        server_url = f"http://{self.release_name}-server:8807/v1/"
        config_content = f'url: "{server_url}"\napi_keys:\n  - "{api_key}"'
        self.kubectl(
            "exec",
            pod_name,
            "--",
            "sh",
            "-c",
            f"printf '%s\\n' '{config_content}' > /tmp/bbctl.yaml",
        )
        bbctl = "bbctl --no-color --config /tmp/bbctl.yaml"

        # Copy test data into the pod
        self.kubectl("cp", "tests/evilcorp.json.gz", f"{pod_name}:/tmp/evilcorp.json.gz")

        # Ingest events using bbctl
        print("Ingesting events...")
        result = self.kubectl(
            "exec",
            pod_name,
            "--",
            "sh",
            "-c",
            f"gunzip -c /tmp/evilcorp.json.gz | {bbctl} event ingest",
            capture_output=True,
            timeout=120,
        )
        print(f"Ingest stdout: {result.stdout}")
        print(f"Ingest stderr: {result.stderr}")
        self.assertEqual(result.returncode, 0, f"Event ingest failed: {result.stderr}")

        # Wait for the watchdog to process events into assets
        print("Waiting for watchdog to process events into assets...")
        assets = []
        for i in range(30):
            result = self.kubectl(
                "exec",
                pod_name,
                "--",
                "sh",
                "-c",
                f"{bbctl} asset list --json",
                capture_output=True,
                check=False,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                assets = [json.loads(line) for line in result.stdout.strip().splitlines() if line.strip()]
                if assets:
                    break
            print(f"  Attempt {i + 1}/30: {len(assets)} assets so far...")
            time.sleep(2)

        print(f"Found {len(assets)} assets")
        self.assertGreater(len(assets), 0, "Should have ingested some assets from evilcorp.json.gz")

    def tearDown(self):
        """If a test fails, dump cluster debug info"""
        failed = False
        outcome = getattr(self, "_outcome", None)
        try:
            if outcome is not None:
                if hasattr(outcome, "errors"):
                    errors = outcome.errors
                elif hasattr(outcome, "result"):
                    result = outcome.result
                    errors = list(getattr(result, "errors", [])) + list(getattr(result, "failures", []))
                else:
                    errors = []
                failed = any(err for _, err in errors)
        except Exception:
            failed = False
        if failed:
            print("\n" + "=" * 80)
            print(f"Test failed: {self.id()} - dumping cluster debug info")
            print("=" * 80)
            self.__class__.dump_cluster_debug_info()


if __name__ == "__main__":
    unittest.main()
