import torch
print("Torch:", torch.__version__)
print("CUDA runtime:", torch.version.cuda)
print("Available?", torch.cuda.is_available())
print("Device:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "None")

