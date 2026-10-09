def walk(node):
    return walk(node.next) if node else None


class Tree:
    def walk(self, node):
        return walk(node)

    def depth(self, node):
        return 1 + self.depth(node.child) if node else 0
