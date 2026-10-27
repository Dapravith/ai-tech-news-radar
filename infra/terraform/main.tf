# Bootstrap only a restricted SHADOW namespace on an existing Kubernetes cluster.
# This does NOT provision a VPS, Kubernetes cluster, Helm release or secret.
# Kubernetes connectivity is supplied explicitly by the operator.
provider "kubernetes" {
  config_path    = pathexpand(var.kubeconfig_path)
  config_context = var.kube_context
}

resource "kubernetes_namespace_v1" "shadow" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/name"       = "ai-tech-news-radar"
      "app.kubernetes.io/part-of"    = "news-intelligence"
      "news-radar/phase"             = "shadow"
      "pod-security.kubernetes.io/enforce" = "restricted"
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

# Limits help keep news experiments from exhausting a small K3s host.
resource "kubernetes_resource_quota_v1" "shadow" {
  metadata {
    name      = "news-radar-budget"
    namespace = kubernetes_namespace_v1.shadow.metadata[0].name
  }
  spec {
    hard = {
      pods              = "10"
      "requests.cpu"    = "500m"
      "requests.memory" = "512Mi"
      "limits.cpu"      = "2"
      "limits.memory"   = "2Gi"
    }
  }
}
