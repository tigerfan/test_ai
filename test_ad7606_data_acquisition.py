from amaranth import *
from amaranth.sim import Simulator, Delay
from amaranth.lib.wiring import connect

from ad7606_data_acquisition import AD7606DataAcquisition

def test_ad7606_data_acquisition():
    dut = AD7606DataAcquisition()
    sim = Simulator(dut)
    sim.add_clock(1e-6)  # 1MHz clock

    def process():
        # 初始化信号
        yield dut.adc_busy.eq(0b000)
        yield dut.adc_data_valid.eq(0b000)
        for i in range(24):
            yield dut.adc_data[i].eq(0)
        yield dut.fsmc_cs.eq(1)
        yield dut.fsmc_rd.eq(1)
        yield dut.fsmc_wr.eq(1)
        yield dut.fsmc_addr.eq(0)

        # 等待一段时间以便状态机启动
        yield Delay(50e-6)  # 增加初始延迟

        # 模拟AD7606转换完成
        yield dut.adc_busy.eq(0b111)
        yield Delay(2e-6)
        yield dut.adc_busy.eq(0b000)
        yield Delay(2e-6)
        yield dut.adc_data_valid.eq(0b111)
        for i in range(24):
            yield dut.adc_data[i].eq(i + 1)  # 模拟不同的数据值
        yield Delay(2e-6)
        yield dut.adc_data_valid.eq(0b000)

        # 等待数据被写入缓冲区
        yield Delay(200e-6)  # 进一步增加延迟以确保所有24个通道的数据被写入

        # 检查写指针是否已更新，多次检查以确保写入完成
        for i in range(5):
            write_ptr = yield dut.write_pointer
            write_debug = yield dut.write_debug_counter
            print(f"Write pointer check {i+1}/5 after write: {write_ptr}, Debug write counter: {write_debug}")
            if write_ptr == 24:
                break
            yield Delay(50e-6)  # 每次检查之间增加延迟
        assert write_ptr == 24, f"Write pointer did not update correctly, expected 24 but got {write_ptr}"
        assert write_debug == 24, f"Debug write counter did not update correctly, expected 24 but got {write_debug}"

        # 检查初始读指针
        read_ptr = yield dut.read_pointer
        print(f"Initial read pointer before read: {read_ptr}")
        assert read_ptr == 0, f"Initial read pointer should be 0, but got {read_ptr}"

        # 强制将读指针设置为0
        yield dut.read_pointer.eq(0)
        yield Delay(2e-6)  # 小延迟以确保设置生效
        read_ptr = yield dut.read_pointer
        print(f"Read pointer after forced reset: {read_ptr}")
        assert read_ptr == 0, f"Read pointer should be 0 after reset, but got {read_ptr}"

        # 模拟FSMC读取操作
        yield dut.fsmc_cs.eq(0)
        yield dut.fsmc_rd.eq(0)
        yield Delay(10e-6)  # 增加读取延迟

        # 尝试读取多个数据点，直到找到非零数据或达到最大尝试次数
        max_attempts = 50
        found_non_zero = False
        for attempt in range(max_attempts):
            # 在每次尝试之前设置读指针
            yield dut.read_pointer.eq(attempt)
            yield Delay(2e-6)  # 每次尝试之间的小延迟
            read_ptr = yield dut.read_pointer
            data = yield dut.fsmc_data
            expected = (read_ptr % 24) + 1
            print(f"Attempt {attempt + 1}/{max_attempts}, Set pointer to {attempt}, Actual read pointer: {read_ptr}, Data: {data}, Expected: {expected}")
            if data != 0:
                found_non_zero = True
                assert data == expected, f"Expected data {expected}, but got {data} at pointer {read_ptr}"
                break

        if not found_non_zero:
            assert False, f"Failed to read non-zero data after {max_attempts} attempts"

        # 读取接下来的几个数据点以验证连续性
        current_ptr = read_ptr
        for _ in range(3):  # 检查接下来的三个数据
            yield dut.read_pointer.eq(current_ptr + 1)
            yield Delay(2e-6)
            read_ptr = yield dut.read_pointer
            data = yield dut.fsmc_data
            expected_val = (read_ptr % 24) + 1
            print(f"Read data at pointer {read_ptr}: {data}, Expected: {expected_val}")
            assert data == expected_val, f"Expected data {expected_val}, but got {data} at pointer {read_ptr}"
            current_ptr = read_ptr

        yield dut.fsmc_cs.eq(1)
        yield dut.fsmc_rd.eq(1)

        # 检查读指针是否已更新
        final_read_ptr = yield dut.read_pointer
        print(f"Final read pointer: {final_read_ptr}")
        assert final_read_ptr == current_ptr, f"Read pointer did not update correctly, expected {current_ptr}, got {final_read_ptr}"

        # 模拟更多转换和读取以测试乒乓缓冲区和中断
        half_buffer_size = dut.half_buffer_size  # 获取半缓冲区大小
        cycles_needed = (half_buffer_size * 24) // 24  # 计算需要多少周期来填充半缓冲区
        print(f"Half buffer size: {half_buffer_size}, Cycles needed to trigger upper half interrupt: {cycles_needed}")
        for cycle in range(cycles_needed + 5):  # 增加转换周期以确保触发中断
            for i in range(24):
                yield dut.adc_data[i].eq(i + 1 + cycle * 24)
            yield dut.adc_data_valid.eq(7)
            yield Delay(1e-6)
            yield dut.adc_data_valid.eq(0)
            yield Delay(500e-6)  # 等待更长的时间以完成写入

            # 打印调试信息
            current_write_ptr = yield dut.write_pointer
            upper_irq = yield dut.irq_upper_half
            lower_irq = yield dut.irq_lower_half
            print(f"Cycle {cycle}: Write pointer = {current_write_ptr}, Upper IRQ = {upper_irq}, Lower IRQ = {lower_irq}")

            # 检查中断
            if cycle >= cycles_needed:  # 在达到半缓冲区大小所需的周期后检查上半部分中断
                assert (yield dut.irq_upper_half) == 1, "Upper half interrupt should be triggered"
                assert (yield dut.irq_lower_half) == 0, "Lower half interrupt should not be triggered"

        # 读取更多数据以测试中断清除
        yield dut.fsmc_cs.eq(0)
        yield dut.fsmc_rd.eq(0)
        for _ in range(dut.half_buffer_size * 24):
            yield Delay(2e-6)
        yield dut.fsmc_cs.eq(1)
        yield dut.fsmc_rd.eq(1)
        yield Delay(2e-6)
        assert (yield dut.irq_upper_half) == 0, "Upper half interrupt should be cleared"

    sim.add_process(process)
    with sim.write_vcd("ad7606_data_acquisition.vcd"):
        sim.run()

if __name__ == "__main__":
    test_ad7606_data_acquisition()
    print("Test completed successfully")
