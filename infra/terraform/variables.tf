variable "kubeconfig_path" {
  description = "Path to your kubeconfig. Never commit kubeconfig or tokens."
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "Explicit Kubernetes context to avoid applying against the wrong cluster."
  type        = string

  validation {
    condition     = length(trimspace(var.kube_context)) > 0
    error_message = "Set a non-empty kube_context; never rely on the implicit current context."
  }
}

variable "namespace" {
  description = "Isolated shadow namespace. Production namespaces are deliberately not supported by this module."
  type        = string
  default     = "news-radar-shadow"

  validation {
    condition     = var.namespace == "news-radar-shadow"
    error_message = "Only news-radar-shadow is allowed in the first deployment phase."
  }
}
