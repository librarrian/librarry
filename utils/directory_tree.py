# TODO - Add docstrings to all methods and classes


class File:
    """Represents a file in the directory tree.
    Contains the full path to the file, the id of the file

    The next() method returns the next directory in the path and removes it from the list.
    The is_ready() method returns true if there are no more directories to traverse, meaning the
    """

    def __init__(self, path: str, id: int):
        self.full_path = path
        self.paths = path.lstrip("/").split("/")
        self.name = self.paths[-1]
        self.id = id

    def next(self) -> str:
        return self.paths.pop(0)

    def to_dict(self):
        return {"id": self.id, "file": self.name}

    def is_ready(self) -> bool:
        return len(self.paths) == 1


class Directory:
    def __init__(self, name: str):
        self.name = name
        self.dirs: dict[str, Directory] = {}
        self.files: list[File] = []

    def add_dir(self, name: str):
        if not name in self.dirs:
            self.dirs[name] = Directory(name)

    def add_file_to_sub_dir(self, dir: str, file: File):
        self.add_dir(dir)
        self.dirs[dir]._add_file(file)

    def _add_file(self, file: File):
        if file.is_ready():
            self.files.append(file)
            return
        dir = file.next()
        self.add_file_to_sub_dir(dir, file)

    def to_dict(self):
        return {
            self.name: [dir.to_dict() for dir in self.dirs.values()]
            + [file.to_dict() for file in self.files]
        }


class Root(Directory):
    def __init__(self):
        super().__init__("/")
        self.all_files: dict[int, File] = {}
        self.curr_id = 1

    def add_file(self, file_path: str):
        file = File(file_path, self.curr_id)
        self.all_files[self.curr_id] = file
        self.curr_id += 1
        self._add_file(file)
