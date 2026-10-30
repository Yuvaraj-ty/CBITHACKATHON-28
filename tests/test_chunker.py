import unittest
from core.chunker import chunk_file, fallback_chunk
from core.models import Chunk


class TestChunker(unittest.TestCase):
    def test_fallback_chunk(self):
        chunks = fallback_chunk("notes.txt", "line 1\nline 2\nline 3", language="text", chunk_id="C42")
        self.assertEqual(len(chunks), 1)
        c = chunks[0]
        self.assertEqual(c.id, "C42")
        self.assertEqual(c.symbol, "<module>")
        self.assertEqual(c.kind, "module")
        self.assertEqual(c.start_line, 1)
        self.assertEqual(c.end_line, 3)
        self.assertEqual(c.language, "text")

    def test_unknown_file_type_fallback(self):
        chunks = chunk_file("data.unknown", "raw binary or text data")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].symbol, "<module>")
        self.assertEqual(chunks[0].kind, "module")

    def test_broken_syntax_never_crashes(self):
        chunks = chunk_file("broken.py", "def :::: (((((( ===")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].symbol, "<module>")

    def test_python_chunking(self):
        code = '''import os
from math import sqrt

def calculate_square_root(val):
    """Compute and print square root."""
    print(val)
    return sqrt(val)

class MathService:
    """Service providing math utilities."""

    def compute(self, x):
        return calculate_square_root(x)
'''
        chunks = chunk_file("services/math.py", code)
        # We expect: calculate_square_root, MathService, MathService.compute
        symbols = {c.symbol: c for c in chunks}
        self.assertIn("calculate_square_root", symbols)
        self.assertIn("MathService", symbols)
        self.assertIn("MathService.compute", symbols)

        # Check function
        fn = symbols["calculate_square_root"]
        self.assertEqual(fn.kind, "function")
        self.assertEqual(fn.docstring, "Compute and print square root.")
        self.assertIn("os", fn.imports)
        self.assertIn("math", fn.imports)
        self.assertIn("sqrt", fn.calls)
        self.assertIn("print", fn.calls)

        # Check class
        cls_chunk = symbols["MathService"]
        self.assertEqual(cls_chunk.kind, "class")
        self.assertEqual(cls_chunk.docstring, "Service providing math utilities.")

        # Check method prefixing
        mth = symbols["MathService.compute"]
        self.assertEqual(mth.kind, "method")
        self.assertIn("calculate_square_root", mth.calls)

    def test_python_ast_dedup_and_sorting(self):
        sample_code = '''import b_mod, a_mod
from z_mod import helper
from a_mod import another

def analyze():
    zebra()
    apple.banana.cherry()
    apple.banana.cherry()
    zebra()
'''
        chunks = chunk_file("sample.py", sample_code)
        self.assertEqual(len(chunks), 1)
        chunk = chunks[0]
        # Imports must be deduplicated and sorted
        self.assertEqual(chunk.imports, ["a_mod", "b_mod", "z_mod"])
        # Calls must be deduplicated, take final attribute, and sorted
        self.assertEqual(chunk.calls, ["cherry", "zebra"])

    def test_javascript_chunking(self):
        code = '''import express from "express";
const fs = require("fs");

// Authenticate user request
export const login = async (req, res) => {
    fs.readFile();
    helper(1);
    [1, 2].map(x => x * 2);
};

/* Regular function doc */
function helper(code) {
    return code;
}

class AuthController {
    // Check session validity
    validateSession() {
        login();
    }
}
'''
        chunks = chunk_file("controllers/auth.js", code)
        symbols = {c.symbol: c for c in chunks}

        # 1. Arrow function assigned to variable declarator
        self.assertIn("login", symbols)
        login_fn = symbols["login"]
        self.assertEqual(login_fn.kind, "function")
        self.assertEqual(login_fn.docstring, "Authenticate user request")
        self.assertIn("express", login_fn.imports)
        self.assertIn("fs", login_fn.imports)
        self.assertIn("readFile", login_fn.calls)
        self.assertIn("helper", login_fn.calls)

        # Verify anonymous inline callback was NOT emitted
        self.assertNotIn("x", symbols)
        self.assertEqual(sum(1 for c in chunks if c.symbol == "login"), 1)

        # 2. Regular function
        self.assertIn("helper", symbols)
        self.assertEqual(symbols["helper"].docstring, "Regular function doc")

        # 3. Class and method prefixing
        self.assertIn("AuthController", symbols)
        self.assertIn("AuthController.validateSession", symbols)
        mth = symbols["AuthController.validateSession"]
        self.assertEqual(mth.kind, "method")
        self.assertEqual(mth.docstring, "Check session validity")
        self.assertIn("login", mth.calls)

    def test_go_chunking(self):
        code = '''package main

import (
    "fmt"
    "net/http"
)

// Server configuration container
type Server struct {
    port int
}

// Handler interface
type Handler interface {
    Handle() error
}

type IgnoredAlias int

// Start boots the server
func (s *Server) Start() {
    fmt.Println(s.port)
}

// Stop terminates the server
func (s Server) Stop() {
    cleanup()
}

func main() {
    http.ListenAndServe(":8080", nil)
}
'''
        chunks = chunk_file("main.go", code)
        symbols = {c.symbol: c for c in chunks}

        # 1. Type specs (struct and interface emitted, alias ignored)
        self.assertIn("Server", symbols)
        self.assertEqual(symbols["Server"].kind, "class")
        self.assertEqual(symbols["Server"].docstring, "Server configuration container")

        self.assertIn("Handler", symbols)
        self.assertEqual(symbols["Handler"].kind, "class")
        self.assertEqual(symbols["Handler"].docstring, "Handler interface")

        self.assertNotIn("IgnoredAlias", symbols)

        # 2. Methods with receiver prefixing (* stripped)
        self.assertIn("Server.Start", symbols)
        mth_start = symbols["Server.Start"]
        self.assertEqual(mth_start.kind, "method")
        self.assertEqual(mth_start.docstring, "Start boots the server")
        self.assertIn("Println", mth_start.calls)

        self.assertIn("Server.Stop", symbols)
        self.assertEqual(symbols["Server.Stop"].kind, "method")

        # 3. Top-level function
        self.assertIn("main", symbols)
        self.assertEqual(symbols["main"].kind, "function")
        self.assertIn("fmt", symbols["main"].imports)
        self.assertIn("net/http", symbols["main"].imports)
        self.assertIn("ListenAndServe", symbols["main"].calls)

    def test_java_chunking(self):
        code = '''package com.company;

import java.util.List;
import java.io.File;

/**
 * Payment processor service.
 */
public class PaymentService {
    // Process single transaction
    public boolean processTransaction(double amount) {
        System.out.println(amount);
        verify();
        return true;
    }
}
'''
        chunks = chunk_file("PaymentService.java", code)
        symbols = {c.symbol: c for c in chunks}

        # Class
        self.assertIn("PaymentService", symbols)
        cls_chunk = symbols["PaymentService"]
        self.assertEqual(cls_chunk.kind, "class")
        self.assertEqual(cls_chunk.docstring, "Payment processor service.")
        self.assertIn("java.util.List", cls_chunk.imports)
        self.assertIn("java.io.File", cls_chunk.imports)

        # Method
        self.assertIn("PaymentService.processTransaction", symbols)
        mth = symbols["PaymentService.processTransaction"]
        self.assertEqual(mth.kind, "method")
        self.assertEqual(mth.docstring, "Process single transaction")
        self.assertIn("println", mth.calls)
        self.assertIn("verify", mth.calls)


if __name__ == "__main__":
    unittest.main()
