from torch.utils.data import Dataset
from torch_geometric.data import Data
import torch


class NewAtomisticDataset(Dataset):
    """
    Compatibility template for SelfConditionedDenoisingAtoms/data/loaders.py.

    The constructor signature matters because the datamodule instantiates datasets as:
    dataset_cls(dataset_root, dataset_arg=dataset_arg, transform=transform)
    """

    def __init__(self, root, dataset_arg=None, transform=None, split="all", **kwargs):
        super().__init__()
        self.root = root
        self.dataset_arg = dataset_arg
        self.transform = transform
        self.split = split

        # Replace this with real sample indexing or file discovery.
        self.samples = []

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        raw = self.samples[idx]

        # Replace this block with real parsing logic.
        pos = torch.tensor(raw["pos"], dtype=torch.float32)
        z = torch.tensor(raw["z"], dtype=torch.long)

        data_kwargs = {
            "pos": pos,
            "z": z,
        }

        # Add scalar targets when available.
        if "y" in raw:
            data_kwargs["y"] = torch.tensor(raw["y"], dtype=torch.float32).reshape(-1)

        # Add force targets for energy/force training.
        if "dy" in raw:
            data_kwargs["dy"] = torch.tensor(raw["dy"], dtype=torch.float32)

        # Add periodic metadata for materials datasets.
        if "cell" in raw:
            data_kwargs["cell"] = torch.tensor(raw["cell"], dtype=torch.float32).reshape(1, 3, 3)
        if "pbc" in raw:
            data_kwargs["pbc"] = torch.tensor(raw["pbc"], dtype=torch.bool).reshape(1, 3)

        data = Data(**data_kwargs)

        if self.transform is not None:
            data = self.transform(data)

        return data

    def get_subset(self, split):
        """
        Implement only if the dataset ships train/val/test splits and you plan
        to run with predefined_splits: true.
        """
        raise NotImplementedError

    def get_atomref(self, max_z=118):
        """
        Implement only if configs use prior_model: Atomref.
        Return shape [max_z, 1] or compatible.
        """
        raise NotImplementedError

    def normalize(self):
        """
        Optional fast path for standardize: true.
        Return (mean, std) tensors for y.
        """
        raise NotImplementedError
