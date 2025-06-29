using System.ComponentModel;
using Microsoft.SemanticKernel;

namespace Plugins;

public class TaxPlugin
{
    [KernelFunction, Description("Calculate the tax amount for a given income and tax rate.")]
    public static double CalculateTax(
        [Description("The user's income")] double income,
        [Description("The tax rate as a percentage (e.g., 20 for 20%)")] double taxRate
    )
    {
        if (income < 0) throw new ArgumentException("Income cannot be negative.");
        if (taxRate < 0 || taxRate > 100) throw new ArgumentException("Tax rate must be between 0 and 100.");
        return income * (taxRate / 100.0);
    }

    [KernelFunction, Description("Calculate the net income after tax for a given income and tax rate.")]
    public static double CalculateNetIncome(
        [Description("The user's income")] double income,
        [Description("The tax rate as a percentage (e.g., 20 for 20%)")] double taxRate
    )
    {
        double tax = CalculateTax(income, taxRate);
        return income - tax;
    }
}
