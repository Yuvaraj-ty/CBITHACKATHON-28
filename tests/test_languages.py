"""
Tests language parsing and chunk extraction across Python, JavaScript, TypeScript, TSX, Java, and Go.
Validates symbols, kinds, line ranges, imports, and calls for each language.
Prints the parse tree if any sample assertion fails.
"""
import unittest
import tree_sitter_language_pack as tsl

from core.chunker import chunk_file
from core.languages import detect_language


def print_parse_tree(code: str, ts_name: str) -> None:
    """Print the tree-sitter parse tree for debugging failing samples."""
    try:
        parser = tsl.get_parser(ts_name)
        tree = parser.parse(code.encode("utf-8"))

        def _print_node(node, depth=0):
            preview = node.text.decode("utf-8", errors="replace").replace("\n", " ")[:30]
            print(f"{'  ' * depth}{node.type} [{preview}]")
            for child in node.children:
                _print_node(child, depth + 1)

        print(f"\n========== TREE-SITTER PARSE TREE ({ts_name}) ==========")
        _print_node(tree.root_node)
        print("=========================================================\n")
    except Exception as e:
        print(f"Failed to print parse tree: {e}")


class TestLanguages(unittest.TestCase):
    def test_python_sample(self):
        code = """import math

class Calculator:
    def add(self, a, b):
        return a + b

def compute(x):
    return math.sqrt(x)
"""
        try:
            chunks = chunk_file("calc.py", code)
            self.assertEqual(len(chunks), 3)

            # Class
            c_calc = chunks[0]
            self.assertEqual(c_calc.symbol, "Calculator")
            self.assertEqual(c_calc.kind, "class")
            self.assertEqual((c_calc.start_line, c_calc.end_line), (3, 5))
            self.assertEqual(c_calc.imports, ["math"])
            self.assertEqual(c_calc.calls, [])

            # Method
            c_add = chunks[1]
            self.assertEqual(c_add.symbol, "Calculator.add")
            self.assertEqual(c_add.kind, "method")
            self.assertEqual((c_add.start_line, c_add.end_line), (4, 5))
            self.assertEqual(c_add.imports, ["math"])
            self.assertEqual(c_add.calls, [])

            # Function
            c_comp = chunks[2]
            self.assertEqual(c_comp.symbol, "compute")
            self.assertEqual(c_comp.kind, "function")
            self.assertEqual((c_comp.start_line, c_comp.end_line), (7, 8))
            self.assertEqual(c_comp.imports, ["math"])
            self.assertEqual(c_comp.calls, ["sqrt"])

        except AssertionError:
            print_parse_tree(code, "python")
            raise

    def test_javascript_sample(self):
        code = """import express from "express";

class Auth {
    verify() {
        return true;
    }
}

const login = async () => {
    express();
};
"""
        try:
            chunks = chunk_file("auth.js", code)
            self.assertEqual(len(chunks), 3)

            # Class
            c_auth = chunks[0]
            self.assertEqual(c_auth.symbol, "Auth")
            self.assertEqual(c_auth.kind, "class")
            self.assertEqual((c_auth.start_line, c_auth.end_line), (3, 7))
            self.assertEqual(c_auth.imports, ["express"])
            self.assertEqual(c_auth.calls, [])

            # Method
            c_verify = chunks[1]
            self.assertEqual(c_verify.symbol, "Auth.verify")
            self.assertEqual(c_verify.kind, "method")
            self.assertEqual((c_verify.start_line, c_verify.end_line), (4, 6))
            self.assertEqual(c_verify.imports, ["express"])
            self.assertEqual(c_verify.calls, [])

            # Top-level arrow function: const login = async () => {}
            c_login = chunks[2]
            self.assertEqual(c_login.symbol, "login")
            self.assertEqual(c_login.kind, "function")
            self.assertEqual((c_login.start_line, c_login.end_line), (9, 11))
            self.assertEqual(c_login.imports, ["express"])
            self.assertEqual(c_login.calls, ["express"])

        except AssertionError:
            print_parse_tree(code, "javascript")
            raise

    def test_typescript_sample(self):
        code = """import { helper } from "./helper";

class UserService {
    getUser(id: string) {
        return id;
    }
}

function formatUser(name: string): string {
    helper(name);
    return name;
}
"""
        try:
            chunks = chunk_file("user.ts", code)
            self.assertEqual(len(chunks), 3)

            # Class
            c_svc = chunks[0]
            self.assertEqual(c_svc.symbol, "UserService")
            self.assertEqual(c_svc.kind, "class")
            self.assertEqual((c_svc.start_line, c_svc.end_line), (3, 7))
            self.assertEqual(c_svc.imports, ["./helper"])
            self.assertEqual(c_svc.calls, [])

            # Method
            c_mth = chunks[1]
            self.assertEqual(c_mth.symbol, "UserService.getUser")
            self.assertEqual(c_mth.kind, "method")
            self.assertEqual((c_mth.start_line, c_mth.end_line), (4, 6))
            self.assertEqual(c_mth.imports, ["./helper"])
            self.assertEqual(c_mth.calls, [])

            # Function
            c_fn = chunks[2]
            self.assertEqual(c_fn.symbol, "formatUser")
            self.assertEqual(c_fn.kind, "function")
            self.assertEqual((c_fn.start_line, c_fn.end_line), (9, 12))
            self.assertEqual(c_fn.imports, ["./helper"])
            self.assertEqual(c_fn.calls, ["helper"])

        except AssertionError:
            print_parse_tree(code, "typescript")
            raise

    def test_tsx_sample(self):
        code = """import React from "react";

class ButtonComponent {
    renderButton() {
        return null;
    }
}

function App() {
    React.createElement("div");
}
"""
        try:
            chunks = chunk_file("button.tsx", code)
            self.assertEqual(len(chunks), 3)

            # Class
            c_btn = chunks[0]
            self.assertEqual(c_btn.symbol, "ButtonComponent")
            self.assertEqual(c_btn.kind, "class")
            self.assertEqual((c_btn.start_line, c_btn.end_line), (3, 7))
            self.assertEqual(c_btn.imports, ["react"])
            self.assertEqual(c_btn.calls, [])

            # Method
            c_mth = chunks[1]
            self.assertEqual(c_mth.symbol, "ButtonComponent.renderButton")
            self.assertEqual(c_mth.kind, "method")
            self.assertEqual((c_mth.start_line, c_mth.end_line), (4, 6))
            self.assertEqual(c_mth.imports, ["react"])
            self.assertEqual(c_mth.calls, [])

            # Function
            c_app = chunks[2]
            self.assertEqual(c_app.symbol, "App")
            self.assertEqual(c_app.kind, "function")
            self.assertEqual((c_app.start_line, c_app.end_line), (9, 11))
            self.assertEqual(c_app.imports, ["react"])
            self.assertEqual(c_app.calls, ["createElement"])

        except AssertionError:
            print_parse_tree(code, "tsx")
            raise

    def test_java_sample(self):
        code = """package com.example;
import java.util.List;

public class Service {
    public Service() {}
    public void execute() {
        System.out.println(1);
    }
}

void helper() {}
"""
        try:
            chunks = chunk_file("Service.java", code)
            self.assertEqual(len(chunks), 4)

            # Class
            c_svc = chunks[0]
            self.assertEqual(c_svc.symbol, "Service")
            self.assertEqual(c_svc.kind, "class")
            self.assertEqual((c_svc.start_line, c_svc.end_line), (4, 9))
            self.assertEqual(c_svc.imports, ["java.util.List"])

            # Constructor
            c_ctor = chunks[1]
            self.assertEqual(c_ctor.symbol, "Service.Service")
            self.assertEqual(c_ctor.kind, "method")
            self.assertEqual((c_ctor.start_line, c_ctor.end_line), (5, 5))
            self.assertEqual(c_ctor.imports, ["java.util.List"])
            self.assertEqual(c_ctor.calls, [])

            # Method
            c_mth = chunks[2]
            self.assertEqual(c_mth.symbol, "Service.execute")
            self.assertEqual(c_mth.kind, "method")
            self.assertEqual((c_mth.start_line, c_mth.end_line), (6, 8))
            self.assertEqual(c_mth.imports, ["java.util.List"])
            self.assertEqual(c_mth.calls, ["println"])

            # Top-level function
            c_hlp = chunks[3]
            self.assertEqual(c_hlp.symbol, "helper")
            self.assertEqual(c_hlp.kind, "function")
            self.assertEqual((c_hlp.start_line, c_hlp.end_line), (11, 11))
            self.assertEqual(c_hlp.imports, ["java.util.List"])

        except AssertionError:
            print_parse_tree(code, "java")
            raise

    def test_go_sample(self):
        code = """package main

import "fmt"

type Server struct {
    port int
}

func (s *Server) Start() {
    fmt.Println(s.port)
}

func run() {
    fmt.Println("run")
}
"""
        try:
            chunks = chunk_file("server.go", code)
            self.assertEqual(len(chunks), 3)

            # Struct type -> kind="class"
            c_srv = chunks[0]
            self.assertEqual(c_srv.symbol, "Server")
            self.assertEqual(c_srv.kind, "class")
            self.assertEqual((c_srv.start_line, c_srv.end_line), (5, 7))
            self.assertEqual(c_srv.imports, ["fmt"])
            self.assertEqual(c_srv.calls, [])

            # Method with pointer receiver -> Server.Start, kind="method"
            c_mth = chunks[1]
            self.assertEqual(c_mth.symbol, "Server.Start")
            self.assertEqual(c_mth.kind, "method")
            self.assertEqual((c_mth.start_line, c_mth.end_line), (9, 11))
            self.assertEqual(c_mth.imports, ["fmt"])
            self.assertEqual(c_mth.calls, ["Println"])

            # Top-level function -> run, kind="function"
            c_run = chunks[2]
            self.assertEqual(c_run.symbol, "run")
            self.assertEqual(c_run.kind, "function")
            self.assertEqual((c_run.start_line, c_run.end_line), (13, 15))
            self.assertEqual(c_run.imports, ["fmt"])
            self.assertEqual(c_run.calls, ["Println"])

        except AssertionError:
            print_parse_tree(code, "go")
            raise


if __name__ == "__main__":
    unittest.main()
