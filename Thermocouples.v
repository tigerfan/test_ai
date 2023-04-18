// Generator : SpinalHDL v1.7.3    git head : ed8004c489ee8a38c2cab309d0447b543fe9d5b8
// Component : Thermocouples

`timescale 1ns/1ps

module Thermocouples (
  input      [15:0]   _zz_1,
  output     [15:0]   _zz_2,
  input               clk,
  input               reset
);

  reg        [15:0]   _zz__zz_3_port0;
  wire                _zz__zz_3_port;
  wire                _zz__zz_2;
  reg [15:0] _zz_3 [0:65534];

  assign _zz__zz_2 = 1'b1;
  initial begin
    $readmemb("Thermocouples.v_toplevel__zz_3.bin",_zz_3);
  end
  always @(posedge clk) begin
    if(_zz__zz_2) begin
      _zz__zz_3_port0 <= _zz_3[_zz_1];
    end
  end

  assign _zz_2 = _zz__zz_3_port0;

endmodule
