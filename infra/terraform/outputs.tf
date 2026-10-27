output "shadow_namespace" {
  description = "Existing-cluster namespace created for safe RSS shadow processing."
  value       = kubernetes_namespace_v1.shadow.metadata[0].name
}
